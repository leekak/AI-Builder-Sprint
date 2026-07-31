# 다시, 그날

> 사진을 보기 전에 기억을 먼저 떠올리고, 원본을 확인한 뒤 새롭게 떠오른 내용을 더해 하나의 추억 카드로 완성하는 회상 다이어리 서비스입니다.

<!-- 데모 스크린샷은 여기에 추가하세요. 예: <img width="400" alt="Image" src="https://github.com/user-attachments/assets/..." /> -->

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
  - 일반 사용자는 볼 수 없는 **동네 추억 카드 삭제** 권한을 가집니다.
  - 삭제해도 사용자가 공유한 비식별 조각 자체는 유지되어, 나중에 다시 동네 카드를 생성할 수 있습니다.

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
- **주요 SQL**:

    ```sql
    SELECT id, place_tag, current_recall_stage
    FROM memories
    WHERE owner_id = ?
      AND recall_completed = false
      AND (
        (current_recall_stage = 1 AND first_recall_at <= now())
        OR (current_recall_stage = 2 AND second_recall_at <= now())
      );

    INSERT INTO recall_sessions (id, memory_id, owner_id, stage, status)
    VALUES (?, ?, ?, ?, 'created');
    ```

### 3-1. 회상 질문과 단계별 힌트

- **대상 사용자**: 회상을 시작한 사용자
- **기능 설명**: 넓은 개방형 질문 하나만 먼저 보여주고, `조금 더 떠올려보기`를 선택하면 감각·분위기 → 활동·장소 순으로 점점 구체적인 힌트를 엽니다. `기억이 잘 나지 않아요`를 선택해도 실패로 기록하지 않습니다.
- **주요 SQL**:

    ```sql
    UPDATE recall_sessions
    SET initial_answer = ?, hint_answers = ?::jsonb, hint_level = ?, answered_at = now()
    WHERE id = ? AND owner_id = ?;
    ```

### 3-2. 원본 공개와 추가 회상

- **대상 사용자**: 답변을 저장한 사용자
- **기능 설명**: 답변 저장 전에는 원본 공개 버튼이 비활성화됩니다. 공개 후에는 원본 사진·코멘트·날짜를 보여주고, 새롭게 떠오른 장면·감정·대화를 추가로 작성할 수 있습니다.
- **주요 SQL**:

    ```sql
    UPDATE recall_sessions
    SET revealed_at = now()
    WHERE id = ? AND owner_id = ?;

    UPDATE recall_sessions
    SET newly_recalled_text = ?, completed_at = now()
    WHERE id = ? AND owner_id = ?;
    ```

## 4. 추억 카드 완성

- **사용자**: 일반 사용자
- **기능 설명**: 회상 전 답변과 공개 후 추가 기억을 Solar가 하나의 이야기로 연결합니다. `(memory_id, stage)`에 유니크 제약을 걸어 1차 회상은 카드를 새로 만들고, 2차 회상은 같은 기억의 카드를 갱신하도록 구분합니다.
- **주요 SQL**:

    ```sql
    -- (memory_id, stage) UNIQUE 제약으로 재회상 시 카드 중복 생성을 방지
    INSERT INTO memory_cards (id, memory_id, recall_id, owner_id, card_title, story, reflection, newly_recalled_details)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?::jsonb);
    ```

### 4-1. 추억 카드 보관함

- **대상 사용자**: 카드 소유자
- **기능 설명**: 완성한 카드를 최신순으로 조회하고, 상세 화면에서 원본 사진과 1·2차 회상 타임라인을 함께 확인합니다. 카드는 숨김 처리와 복구가 가능하며, 영구 삭제와는 구분됩니다.
- **주요 SQL**:

    ```sql
    SELECT * FROM memory_cards
    WHERE owner_id = ? AND archived = false
    ORDER BY created_at DESC;

    UPDATE memory_cards SET archived = true WHERE id = ? AND owner_id = ?;
    ```

### 4-2. 사진 없는 카드의 AI 이미지 생성

- **대상 사용자**: 원본 사진이 없는 카드의 소유자
- **기능 설명**: 사진이 있는 카드는 원본을 그대로 쓰고 이미지 생성 버튼 자체를 숨깁니다. 사진이 없을 때만 카드 내용을 바탕으로 Gemini(Nano Banana)가 이미지를 생성하며, 원본 사진은 절대 Google API로 전송되지 않습니다.
- **주요 SQL**:

    ```sql
    UPDATE memory_cards
    SET generated_image_path = ?, image_generation_status = 'completed', image_generated_at = now()
    WHERE id = ? AND owner_id = ?;
    ```

## 5. 동네 추억 카드

### 5-1. 공유 미리보기와 비식별화

- **대상 사용자**: 카드를 완성한 사용자 (opt-in)
- **기능 설명**: 공유 버튼을 눌러도 바로 저장하지 않습니다. Solar가 이름·소속·경로 등을 제거한 미리보기 문장을 10분 유효한 서버 서명과 함께 보여주고, 사용자가 최종 확인해야 실제로 저장됩니다.
- **주요 SQL**:

    ```sql
    INSERT INTO town_contributions (id, card_id, memory_id, recall_id, owner_id, contributor_key, place_tag, pre_reveal_text, post_reveal_text)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    ```

### 5-2. 동네 카드 생성 (최소 3명)

- **대상 사용자**: 수동 트리거(발표자/관리자 화면의 버튼)
- **기능 설명**: 같은 장소 태그에 서로 다른 사용자 3명의 조각이 모이면 카드를 생성합니다. 기여자 수는 레코드 수가 아니라 서로 다른 사용자 수로 판정하며, 같은 사용자의 여러 조각은 하나로 묶어 한 명으로 집계합니다.
- **주요 SQL**:

    ```sql
    SELECT COUNT(DISTINCT COALESCE(contributor_key, owner_id)) AS contributors
    FROM town_contributions
    WHERE place_tag = ?;

    INSERT INTO town_cards (id, place_tag, contributors, card_title, story, reflection, source_contribution_ids, published_contributor_keys, version)
    VALUES (?, ?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, 1);
    ```

### 5-3. 동네 기억 지도

- **사용자**: 모든 사용자
- **기능 설명**: Leaflet과 실제 부산 16개 구·군 경계 데이터를 이용해 장소별 기여 현황을 지도에서 확인할 수 있습니다.
- **주요 SQL**:

    ```sql
    SELECT place_tag, COUNT(DISTINCT COALESCE(contributor_key, owner_id)) AS contributors
    FROM town_contributions
    GROUP BY place_tag;
    ```

## 6. 관리자 인증과 동네 카드 삭제

- **사용자**: 관리자
- **기능 설명**: 관리자 아이디/비밀번호로 로그인하면 JWT를 발급하고, 이 토큰이 있어야만 동네 카드를 삭제할 수 있습니다. 일반 사용자에게는 삭제 버튼 자체가 보이지 않습니다.
- **주요 SQL**:

    ```sql
    DELETE FROM town_cards WHERE id = ?;  -- require_admin_account 의존성 통과 후에만 실행
    ```

## 7. 개인 기억 삭제 정책

- **대상 사용자**: 기억 소유자
- **기능 설명**: 원본 사진·코멘트·회상 세션·개인 카드는 완전히 삭제합니다. 다만 이미 발행된 동네 카드에 쓰인 조각은 카드를 깨뜨리지 않도록 익명 보존 테이블로 옮깁니다.
- **주요 SQL**:

    ```sql
    -- 이미 발행된 동네 카드에 쓰인 조각은 사용자 연결을 제거하고 보존
    INSERT INTO town_archived_fragments (id, place_tag, contributor_key, pre_reveal_text, post_reveal_text)
    SELECT ?, place_tag, contributor_key, pre_reveal_text, post_reveal_text
    FROM town_contributions WHERE memory_id = ?;

    DELETE FROM memories WHERE id = ? AND owner_id = ?;  -- CASCADE로 회상 세션·개인 카드도 함께 삭제
    ```

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

# 5️⃣ 팀원의 역할 배분

> 아래 이름·역할은 초안입니다. 실제 담당과 다르면 알려주세요 — 정확한 내용으로 채워드릴게요.

- 이학진(팀장)
- 김동현
- 김진우

---

# 6️⃣ 프로젝트 실행 방법

1. Python 3.11 이상 가상환경을 만들고 의존성을 설치합니다.

    ```bash
    python -m venv venv
    source venv/bin/activate      # Windows: venv\Scripts\activate
    python -m pip install -r requirements.txt
    ```

2. `.env.example`을 `.env`로 복사합니다. 기본값(`AI_MODE=mock`, `STORAGE_BACKEND=local`, SQLite)만으로도 외부 키 없이 전체 플로우가 동작합니다.

    ```bash
    cp .env.example .env
    ```

3. 서버를 실행합니다.

    ```bash
    python run.py
    ```

4. 아래 주소로 접속합니다.

    - 데모 UI: [http://127.0.0.1:8000/demo/](http://127.0.0.1:8000/demo/)
    - Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
    - 상태 확인: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

5. (선택) 동네 카드 데모용 시드 데이터를 넣고, 동네 카드를 생성해봅니다.

    ```bash
    python scripts/seed.py
    ```

    ```text
    POST /archive/places/광안리/card
    ```

6. (선택) 자동 테스트와 서버 스모크 테스트를 실행합니다.

    ```bash
    python -m pytest
    python scripts/smoke_test.py   # 서버가 실행 중이어야 합니다
    ```

Supabase(Postgres+Storage), Upstage(Solar·Document Parse·Information Extract), Gemini(카드 이미지 생성), 관리자 계정, 회상 데모 압축 모드 등 실제 서비스 연동에 필요한 모든 환경변수와 정책은 [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)와 [`VALIDATION.md`](VALIDATION.md)에 자세히 정리되어 있습니다.

---
