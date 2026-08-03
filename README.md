# 다시, 그날

> 사진을 보기 전에 기억을 먼저 떠올리고, 원본을 확인한 뒤 새롭게 떠오른 내용을 더해 하나의 추억 카드로 완성하는 회상 다이어리 서비스입니다.

<img width="400" alt="image" src="https://github.com/user-attachments/assets/ad5a2d8d-1a06-4ba4-8104-de72cfc9cdc9" />
<img width="400" alt="image" src="https://github.com/user-attachments/assets/f3d6d275-9b91-4880-94c8-a7e83068b819" />
<img width="400" alt="image" src="https://github.com/user-attachments/assets/1823503a-6011-46bd-b945-3ac5845f20ef" />
<img width="400" alt="image" src="https://github.com/user-attachments/assets/e5742d92-064c-4c9e-9df3-baeba86410ef" />


# 1️⃣ 프로젝트 개요

**프로젝트 주제**

이 웹 애플리케이션은 **사진과 코멘트를 바로 다시 보여주지 않는 회상 다이어리**입니다. 기억을 등록하면 일정 시간(7일, 30일)이 지난 뒤 원본을 숨긴 채 먼저 기억을 떠올리게 하고, 원본을 공개한 다음 새롭게 떠오른 내용을 더해 하나의 추억 카드로 완성합니다.

**프로젝트 목표**

이 서비스는 **저장은 기억을 지켜주지 않는다, 기억은 다시 떠올리는 과정(인출)에서 강화된다**는 인지심리학적 원리를 개인의 기억뿐 아니라 사라져가는 장소의 기억에도 적용하는 것을 목표로 합니다. AI는 사용자를 채점하는 역할이 아니라 회상을 유도하는 질문을 만들고, 회상 전후의 내용을 자연스럽게 하나의 이야기로 연결하는 역할만 합니다.

**차별성 및 장점**

1. **회상 우선 흐름:** 기존의 사진 다이어리와 달리, 원본을 즉시 보여주지 않고 **개방형 질문 → 자유 회상 → 원본 공개** 순서를 강제합니다. 정답을 맞히는 문제가 아니라 넓은 질문에서 시작해 단계적으로 구체적인 단서를 열람하는 방식으로, 사용자가 "틀렸다"는 느낌을 받지 않도록 설계했습니다.
2. **1·2차 회상과 카드 누적:** 하나의 기억은 7일 뒤와 30일 뒤 두 번 회상되며, 두 번째 회상에서 새롭게 떠오른 내용은 새 카드가 아니라 **기존 카드에 이어 붙습니다.** 회상 횟수가 아니라 원본 기억을 기준으로 카드를 관리합니다.
3. **동네 추억 카드:** 개인 회상 메커니즘(회상 → 원본 공개 → 새 기억 추가 → AI가 하나의 이야기로 연결)을 지역 단위로 그대로 확장했습니다. 같은 장소를 회상한 서로 다른 사용자 3명의 익명 조각이 모이면 공동체 추억 카드가 만들어져, 사라져가는 동네의 기억도 함께 보존합니다.
4. **강력한 개인정보 보호 파이프라인:** 동네 공유 전 Solar가 이름·소속·경로 등을 비식별화하고, Information Extract로 민감 후보를 한 번 더 검출한 뒤, 백엔드가 최종 결과에 남은 차단 표현을 강제로 검사합니다. 사용자는 실제로 저장될 문장을 미리 확인하고 동의해야만 공유가 진행됩니다.

**사용 언어 및 라이브러리** : Python, FastAPI, SQLAlchemy, SQLite/Supabase(Postgres), Supabase Storage, Upstage(Solar LLM·Document Parse·Information Extract), Google Gemini(Nano Banana), Leaflet.js

---

# 2️⃣ 사용자(Role)

- **일반 사용자 (User)**:
  - 사진(0~1장)과 코멘트로 기억을 등록하고, 회상 시점이 되면 질문에 답하며 회상합니다.
  - 원본 공개 후 새롭게 떠오른 기억을 추가해 추억 카드를 완성하고, 카드를 보관·숨김 처리할 수 있습니다.
  - opt-in으로 동의한 경우에만 비식별화된 회상 조각을 동네 추억 카드 재료로 공유합니다.
  - 다른 사용자의 기억·카드에는 접근할 수 없습니다(`owner_id` 기준으로 완전히 격리).
- **관리자 (Admin)**:
  - 별도 로그인(아이디/비밀번호 + JWT)을 통해서만 접근할 수 있습니다.
  - 일반 사용자는 볼 수 없는 **동네 추억 카드 삭제·복구** 권한을 가집니다.
  - 삭제된 카드는 공개 목록과 지도에서 숨겨지며, 관리자 화면에서 이야기·버전·기여 정보를 유지한 채 복구할 수 있습니다.

---

# 3️⃣ 기능

## 1. 기억 등록

- **사용자**: 일반 사용자
- **기능**: 사진 0~1장, 코멘트, 기억 날짜, 자유 입력 장소(`place_label`)를 `multipart/form-data`로 등록합니다. 등록과 동시에 1차(7일 뒤)·2차(30일 뒤) 회상 시각을 계산해 저장합니다.
- **주요 SQL**:

    ```sql
    INSERT INTO memories (
      id, owner_id, comment, memory_date, place_label,
      image_path, image_filename, image_content_type, use_ocr,
      first_recall_at, second_recall_at, current_recall_stage, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'registered');
    ```

### 1-1. 사진 속 텍스트 인식 (조건부 OCR)

- **대상 사용자**: 일반 사용자
- **기능 설명**: 영화표·영수증처럼 사진 속에 텍스트가 있을 때만 사용자가 직접 `use_ocr`을 선택합니다. 이미지가 없는데 OCR을 요청하면 400 오류로 차단합니다. Document Parse 결과는 이후 Information Extract·Solar 분석에 함께 사용됩니다.
- **주요 SQL**:

    ```sql
    UPDATE memories
    SET ocr_status = 'completed', ocr_text = ?
    WHERE id = ? AND owner_id = ?;
    ```

## 2. 기억 맥락 분석

- **사용자**: 일반 사용자 (등록 직후 자동 실행)
- **기능 설명**: Information Extract가 코멘트(+OCR 결과)에서 사람·장소·활동·분위기를 사실 기반으로 구조화하고, Solar가 그 결과를 바탕으로 제목·요약·회상 단서(`recall_cues`)를 생성합니다. 원문에 없는 사건·감정은 만들어내지 않습니다.
- **주요 SQL**:

    ```sql
    UPDATE memories
    SET extraction_status = 'completed', extracted_context = ?::jsonb
    WHERE id = ?;

    UPDATE memories
    SET analysis_status = 'completed', analysis = ?::jsonb
    WHERE id = ?;
    ```

## 3. 오늘의 회상

- **사용자**: 일반 사용자
- **기능 설명**: 회상 시각이 지난 기억만 조회합니다. 원본 코멘트·이미지는 응답에 포함하지 않고, 같은 날짜에 여러 기억이 있으면 순서(`day_sequence`)와 범주형 단서로만 구분합니다.


### 3-1. 회상 질문과 단계별 힌트

- **대상 사용자**: 회상을 시작한 사용자
- **기능 설명**: 넓은 개방형 질문 하나만 먼저 보여주고, `조금 더 떠올려보기`를 선택하면 감각·분위기 → 활동·장소 순으로 점점 구체적인 힌트를 엽니다. `기억이 잘 나지 않아요`를 선택해도 실패로 기록하지 않습니다.


### 3-2. 원본 공개와 추가 회상

- **대상 사용자**: 답변을 저장한 사용자
- **기능 설명**: 답변 저장 전에는 원본 공개 버튼이 비활성화됩니다. 공개 후에는 원본 사진·코멘트·날짜를 보여주고, 새롭게 떠오른 장면·감정·대화를 추가로 작성할 수 있습니다.


## 4. 추억 카드 완성

- **사용자**: 일반 사용자
- **기능 설명**: 원본 코멘트와 원본 공개 후 새롭게 떠오른 내용만 Solar가 하나의 이야기로 연결합니다. 원본 공개 전 답변(초기 답변·힌트 답변)은 사용자가 아직 원본을 보기 전에 떠올린 추측이라 실제와 다를 수 있어, 카드 이야기에는 포함하지 않습니다. `(memory_id, stage)`에 유니크 제약을 걸어 1차 회상은 카드를 새로 만들고, 2차 회상은 같은 기억의 카드를 갱신하도록 구분합니다.

### 4-1. 추억 카드 보관함

- **대상 사용자**: 카드 소유자
- **기능 설명**: 완성한 카드를 최신순으로 조회하고, 상세 화면에서 원본 사진과 1·2차 회상 타임라인을 함께 확인합니다. 카드는 숨김 처리와 복구가 가능하며, 영구 삭제와는 구분됩니다.


### 4-2. 사진 없는 카드의 AI 이미지 생성

- **대상 사용자**: 원본 사진이 없는 카드의 소유자
- **기능 설명**: 사진이 있는 카드는 원본을 그대로 쓰고 이미지 생성 버튼 자체를 숨깁니다. 사진이 없을 때만 원본 코멘트와 1·2차 회상에서 원본 공개 후 새롭게 떠오른 내용만으로 Gemini(Nano Banana)가 이미지를 생성합니다. 원본 공개 전 답변은 실제와 다른 추측일 수 있어 이미지 생성 입력에서 제외하며, 원본 사진은 절대 Google API로 전송되지 않습니다.


## 5. 동네 추억 카드

### 5-1. 공유 미리보기와 비식별화

- **대상 사용자**: 카드를 완성한 사용자 (opt-in)
- **기능 설명**: 공유 버튼을 눌러도 바로 저장하지 않습니다. Solar가 이름·소속·경로 등을 제거한 뒤, 원본 공개 전/후 회상을 하나로 합친 요약 문장 한 개를 10분 유효한 서버 서명과 함께 보여주고, 사용자가 최종 확인해야 실제로 저장됩니다.


### 5-2. 동네 카드 생성 (최소 3명, 자동)

- **대상 사용자**: 시스템(카드를 동네에 공유하는 순간 자동 실행) + 관리자(수동 재시도)
- **기능 설명**: 카드를 동네에 공유하는 순간 서버가 같은 장소 태그의 기여자 수를 바로 확인해, 서로 다른 사용자 3명이 모이면 관리자 개입 없이 카드를 자동으로 생성·갱신합니다(`generate_town_card_if_ready`). 이 자동 생성이 실패해도 공유 자체는 막지 않고 조용히 넘어가며, 필요하면 `POST /archive/places/{place_tag}/card`로 관리자가 수동 재시도할 수 있습니다. 기여자 수는 레코드 수가 아니라 서로 다른 사용자 수로 판정하며, 같은 사용자의 여러 조각은 하나로 묶어 한 명으로 집계합니다.

### 5-3. 동네 기억 지도

- **사용자**: 모든 사용자
- **기능 설명**: Leaflet과 실제 부산 16개 구·군 경계 데이터를 이용해 장소별 기여 현황을 지도에서 확인할 수 있습니다.


## 6. 관리자 인증과 동네 카드 삭제·복구

- **사용자**: 관리자
- **기능 설명**: 관리자 아이디/비밀번호로 로그인하면 JWT를 발급하고, 이 토큰이 있어야만 동네 카드를 삭제하거나 복구할 수 있습니다. 삭제는 영구 제거가 아니라 공개 목록과 지도에서 숨기는 소프트 삭제입니다. 같은 장소에 새 활성 카드가 생긴 경우 중복 공개를 막기 위해 기존 삭제 카드의 복구를 차단합니다.

기존 Supabase 프로젝트에는 `sql/migrations/006_town_card_soft_delete.sql`을 SQL Editor에서 한 번 실행해야 합니다. 기능 적용 이전에 영구 삭제된 카드는 원본 행이 남아 있지 않아 복구할 수 없습니다.

관리자는 장소를 선택한 뒤 **지역 카드 내용 다시 만들기**를 눌러 기존 공유 조각을 최신 개인정보 보호 규칙으로 다시 비식별화하고 지역 카드를 새 버전으로 재생성할 수 있습니다. 이 과정은 원본 사진·코멘트를 지역 카드 재료로 사용하지 않고 사용자가 작성한 회상 답변만 다시 처리합니다. 이름·소속·정확한 이동 경로는 제거하되, 골목·생활 소리·화분·작은 가게처럼 개인을 특정하지 않는 지역 생활 정보는 보존합니다.

## 7. 개인 기억 삭제 정책

- **대상 사용자**: 기억 소유자
- **기능 설명**: 원본 사진·코멘트·회상 세션·개인 카드는 완전히 삭제합니다. 다만 이미 발행된 동네 카드에 쓰인 조각은 카드를 깨뜨리지 않도록 익명 보존 테이블로 옮깁니다.


---

# 4️⃣ 데이터베이스 스키마

**PK : 진하게**, <u>FK : 밑줄</u>

| 테이블명 | 컬럼명 |
| --- | --- |
| memories | **id** varchar(36), owner_id varchar(128), comment text, memory_date date, place_label varchar(255), image_path/filename/content_type, use_ocr boolean, ocr_status/ocr_text/ocr_error, extraction_status/extracted_context(jsonb)/extraction_error, analysis_status/analysis(jsonb)/analysis_error, first_recall_at/second_recall_at timestamptz, current_recall_stage int, recall_completed boolean, place_tag, suggested_place_tag, share_to_town boolean, status, created_at/updated_at |
| recall_sessions | **id** varchar(36), <u>memory_id</u> → memories, owner_id, stage int, status, questions(jsonb), initial_answer, hint_answers(jsonb), hint_level int, memory_not_recalled boolean, newly_recalled_text, started_at/answered_at/revealed_at/completed_at *(UNIQUE: memory_id+stage)* |
| memory_cards | **id**, <u>memory_id</u> → memories, <u>recall_id</u> → recall_sessions(UNIQUE), owner_id, card_title, story, reflection, newly_recalled_details(jsonb), archived boolean, shared_to_town boolean, place_tag, generated_image_path/filename/content_type, image_generation_status/mode/style/prompt, image_generated_at, created_at/updated_at |
| town_contributions | **id**, <u>card_id</u> → memory_cards(UNIQUE), <u>memory_id</u> → memories, <u>recall_id</u> → recall_sessions, owner_id, contributor_key, place_tag, pre_reveal_text, post_reveal_text, created_at |
| town_archived_fragments | **id**, place_tag, contributor_key, pre_reveal_text, post_reveal_text, created_at *(owner_id/memory_id/card_id/recall_id 없음 — 작성자 재연결 불가)* |
| town_cards | **id**, place_tag, contributors int, card_title, story, reflection, source_contribution_ids(jsonb), published_contributor_keys(jsonb), version int, created_at/updated_at |

전체 DDL은 [`sql/supabase_schema.sql`](sql/supabase_schema.sql), 스키마 변경 이력은 [`sql/migrations/`](sql/migrations)에 있습니다.

---

# 5️⃣ 팀장 및 팀원


- 이학진(팀장)
- 김동현
- 김진우

---

# 6️⃣ 로컬 실행 가이드

1. Python 3.11 이상 가상환경을 만들고 의존성을 설치합니다. (개발 환경은 Python 3.14 기준으로 검증했습니다.)

    ```bash
    python -m venv venv
    source venv/bin/activate      # Windows: venv\Scripts\activate
    python -m pip install -r requirements.txt
    ```

2. `.env.example`을 `.env`로 복사합니다. 기본값(`AI_MODE=mock`, `CARD_IMAGE_MODE=mock`, `STORAGE_BACKEND=local`, SQLite)만으로도 외부 키 없이 전체 플로우가 동작합니다.

    ```bash
    cp .env.example .env
    ```

3. 서버를 실행합니다. (`uvicorn` reload 모드로 켜지며, `app/main.py`의 `create_app()`이 시작 시 SQLite 테이블을 자동 생성합니다.)

    ```bash
    python run.py
    ```

4. 아래 주소로 접속합니다.

    - 데모 UI: [http://127.0.0.1:8000/demo/](http://127.0.0.1:8000/demo/) — 상단 `사용자 로그인`에 `user1`처럼 원하는 아이디를 넣고 로그인하면 새로고침해도 그 사용자로 유지됩니다.
    - Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
    - 상태 확인: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) — 현재 `ai_mode`·`storage_backend`·`demo_mode` 등 실행 설정을 그대로 보여줍니다.
    - 관리자 로그인: `.env`의 `ADMIN_USERNAME`/`ADMIN_PASSWORD`(기본값 `admin`/미설정 — 아래 환경변수 표 참고)로 로그인하면 동네 추억 카드 관리 화면으로 전환됩니다.

5. (선택) 동네 카드 데모용 시드 데이터를 넣고, 동네 카드를 생성해봅니다. 카드 공유 3명이 모이면 서버가 자동으로 동네 카드를 만들지만, 아래 API로 수동 재시도할 수도 있습니다.

    ```bash
    python scripts/seed.py
    ```

    ```text
    POST /archive/places/광안리/card
    ```

6. (선택) 자동 테스트와 서버 스모크 테스트를 실행합니다.

    ```bash
    python -m pytest         # 41개 테스트, mock AI·SQLite·로컬 Storage로 격리 실행
    python scripts/smoke_test.py   # 서버가 실행 중이어야 합니다
    ```

---

# 7️⃣ 실행 · 배포 환경 정보

> 현재 이 프로젝트는 로컬 개발 환경(SQLite·로컬 Storage)으로만 실제 운영 중이며, 아직 어디에도 배포되어 있지 않습니다. 아래 "실 서비스 배포" 열은 배포할 때 어떻게 전환하면 되는지 안내하는 것이지, 지금 이미 그렇게 떠 있다는 뜻이 아닙니다.

| 구분 | 로컬 개발(기본값) | 실 서비스 배포 |
| --- | --- | --- |
| 실행 방식 | `python run.py` (uvicorn reload) | `Dockerfile` 기준 `uvicorn app.main:app --host 0.0.0.0 --port 8000` (reload 없이 실행) |
| 데이터베이스 | SQLite (`sqlite:///./data/memory_recall.db`), 서버 시작 시 테이블 자동 생성 | Supabase PostgreSQL — `DATABASE_URL`을 Supabase Pooler 연결 문자열로 교체 (`sql/supabase_schema.sql`로 스키마 생성, `sql/migrations/`가 변경 이력) |
| 파일 저장소 | `STORAGE_BACKEND=local`, `./data/uploads`에 저장 | `STORAGE_BACKEND=supabase` — `SUPABASE_URL`·`SUPABASE_SERVICE_ROLE_KEY` 필요 |
| AI 처리 | `AI_MODE=mock` — 외부 API 호출 없이 고정된 결과 반환 | `AI_MODE=upstage`(또는 실패 시 mock으로 넘어가는 `auto`) — `UPSTAGE_API_KEY` 필요 |
| 카드 이미지 생성 | `CARD_IMAGE_MODE=mock` | `CARD_IMAGE_MODE=gemini` — `GEMINI_API_KEY` 필요 |
| 사용자 인증 | `AUTH_MODE=demo` — 프론트 상단 로그인 입력창의 아이디를 `X-User-Id`로 그대로 사용(브라우저 `localStorage`에 저장되어 새로고침에도 유지, 실제 신원 확인 아님) | `AUTH_MODE=supabase` — Supabase Auth가 발급한 JWT를 검증(`SUPABASE_JWT_SECRET` 필요), 프론트 로그인 연동은 아직 미구현 |
| 정적 파일 캐시 | `ENVIRONMENT=development`일 때 `/demo` 응답에 `no-cache` 헤더를 강제해 JS/CSS 수정이 새로고침에 바로 반영됨 (`app/main.py`) | `ENVIRONMENT=production`이면 이 미들웨어가 빠져 브라우저 캐시가 정상 동작 |
| CORS | `CORS_ORIGINS=["*"]` (기본값) | 배포 도메인만 허용하도록 좁혀서 설정 |
| Docker 배포 | — | `docker build -t memory-recall .` 후 `docker run -p 8000:8000 --env-file .env memory-recall` (이미지에 한글 렌더링용 `fonts-noto-cjk` 포함) |

관리자 계정, 회상 데모 압축 모드 등 시나리오별 실행 팁은 [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)에, 자동/수동 검증 기록은 [`VALIDATION.md`](VALIDATION.md)에 자세히 정리되어 있습니다.

여러 개발자가 동일한 Supabase 프로젝트에 접속할 때 Session Pooler(`:5432`)의 연결 한도를 소진하지 않도록, Pooler URL에서는 요청 종료 시 DB 연결을 즉시 반환합니다. 연결 한도 오류가 계속되면 실행 중인 팀원 서버를 모두 재시작하거나 Supabase의 Transaction Pooler(`:6543`) URL을 사용하세요. Transaction Pooler URL은 코드에서 psycopg prepared statement를 자동으로 비활성화합니다.

---

# 8️⃣ 환경변수 정보

`.env.example`을 복사해 값을 채웁니다. **`.env`는 `.gitignore`에 포함되어 있어 커밋되지 않습니다.**

| 분류 | 변수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| 기본 실행 | `ENVIRONMENT` | `development` | `production`이 아니면 `/demo` 정적 파일에 no-cache 헤더를 강제합니다. |
| | `DEBUG` | `false` | 디버그 로깅 여부. |
| | `DATABASE_URL` | `sqlite:///./data/memory_recall.db` | SQLite 또는 Supabase Postgres 연결 문자열. |
| | `AUTO_CREATE_TABLES` | `true` | 서버 시작 시 SQLAlchemy 테이블을 자동 생성할지 여부. **주의**: 없는 테이블만 새로 만들 뿐, 이미 있는 테이블에 컬럼을 추가하는 마이그레이션은 하지 않습니다. 팀원이 스키마를 바꾼 커밋을 받은 뒤에는 서버 재시작만으로 반영되지 않고, 로컬 SQLite 파일(`data/memory_recall.db`)을 지우고 다시 생성하거나 `sql/migrations/`의 해당 마이그레이션을 직접 적용해야 합니다. |
| 인증 | `AUTH_MODE` | `demo` | `demo` \| `header` \| `supabase`. `header`는 모든 요청에 `X-User-Id`가 필요, `supabase`는 JWT 검증. |
| | `DEMO_USER_ID` | `demo-user` | `AUTH_MODE=demo`에서 사용자 미지정 시 기본 아이디. |
| | `SUPABASE_JWT_SECRET` | (없음) | `AUTH_MODE=supabase`일 때 **필수**. |
| 저장소 | `STORAGE_BACKEND` | `local` | `local` \| `supabase`. |
| | `LOCAL_STORAGE_DIR` | `./data/uploads` | 로컬 저장 경로. |
| | `MAX_UPLOAD_MB` | `10` | 업로드 이미지 최대 용량(MB). |
| | `ALLOWED_IMAGE_TYPES` | `image/jpeg,image/png,image/webp` | 허용 이미지 MIME 타입. |
| | `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | (없음) | `STORAGE_BACKEND=supabase`일 때 **필수**. |
| | `SUPABASE_STORAGE_BUCKET` | `memory-images` | Supabase Storage 버킷 이름. |
| AI (Upstage) | `AI_MODE` | `mock` | `mock`(외부 호출 없음) \| `auto`(키 있으면 Upstage, 실패 시 mock) \| `upstage`(실패 시 그대로 오류). |
| | `AI_FALLBACK_TO_MOCK` | `true` | `auto` 모드에서 Upstage 실패 시 mock으로 대체할지 여부. |
| | `UPSTAGE_API_KEY` | (없음) | `AI_MODE=upstage`일 때 **필수**. |
| | `UPSTAGE_BASE_URL` | `https://api.upstage.ai/v1` | Upstage API 베이스 URL. |
| | `UPSTAGE_SOLAR_MODEL` | `solar-pro3` | 제목·요약·질문·비식별화 등에 쓰는 LLM. |
| | `UPSTAGE_DOCUMENT_PARSE_URL` / `_MODEL` | 기본 제공 | 사진 속 글자 OCR. |
| | `UPSTAGE_INFORMATION_EXTRACT_URL` / `_MODEL` | 기본 제공 | 사람·장소·활동·분위기 구조화 추출. |
| | `UPSTAGE_TEXT_RENDER_FONT_PATH` | (자동 탐색) | 텍스트만 있는 기억을 이미지로 렌더링할 때 쓸 한글 글꼴 경로. |
| | `UPSTAGE_TIMEOUT_SECONDS` | `60` | Upstage 호출 타임아웃(초). |
| 카드 이미지 | `CARD_IMAGE_GENERATION_ENABLED` | `true` | 사진 없는 카드의 AI 이미지 생성 기능 자체를 켤지 여부. |
| | `CARD_IMAGE_MODE` | `mock` | `mock` \| `auto` \| `gemini`. |
| | `GEMINI_API_KEY` | (없음) | `CARD_IMAGE_MODE=gemini`일 때 **필수**. |
| | `NANO_BANANA_MODEL` | `gemini-3.1-flash-image` | 카드 이미지 생성 모델. |
| | `NANO_BANANA_TIMEOUT_SECONDS` | `120` | Gemini 호출 타임아웃(초). |
| 회상 일정 | `DEMO_MODE` | `false` | `true`면 하루를 `DEMO_DAY_SECONDS`초로 압축(발표·데모용). |
| | `DEMO_DAY_SECONDS` | `2` | 데모 모드에서 하루에 해당하는 초. |
| | `FIRST_RECALL_DAYS` / `SECOND_RECALL_DAYS` | `7` / `30` | 1차·2차 회상까지 걸리는 기본 일수. |
| | `ALLOW_EARLY_RECALL` | `false` | 회상 시각 이전에도 조회를 허용할지 여부(테스트용). |
| 동네 추억 카드 · 관리자 | `TOWN_MIN_CONTRIBUTORS` | `3` | 동네 카드 생성에 필요한 최소 서로 다른 기여자 수. |
| | `ADMIN_KEY` | (없음) | 레거시/보조 관리자 키(선택). |
| | `ADMIN_USERNAME` | `admin` | 관리자 로그인 아이디. |
| | `ADMIN_PASSWORD` | (없음) | 관리자 로그인 비밀번호. 설정 시 `ADMIN_TOKEN_SECRET`도 **필수**. |
| | `ADMIN_TOKEN_SECRET` | (없음) | 관리자 JWT 서명 비밀값. |
| | `ADMIN_TOKEN_HOURS` | `8` | 관리자 세션 유효 시간. |
| | `SHARE_PREVIEW_SECRET` | `development-only-change-me` | 동네 공유 미리보기 서명 비밀값. 배포 시 충분히 긴 무작위 값으로 교체. |
| | `PLACE_TAGS` | 부산 50개 지역 목록(JSON) | 동네 카드에 쓰는 표준 지역 화이트리스트. |
| 기타 | `CORS_ORIGINS` | `["*"]` | 허용할 프론트엔드 오리진 목록(JSON). |

값을 잘못 넣으면 서버가 뜨지 않고 바로 원인을 알려줍니다 (`app/config.py`의 `validate_runtime_configuration()`): 예를 들어 `AI_MODE=upstage`인데 `UPSTAGE_API_KEY`가 비어 있거나, `ADMIN_PASSWORD`만 설정하고 `ADMIN_TOKEN_SECRET`을 빼먹으면 시작 시점에 `RuntimeError`로 즉시 실패합니다.

---
