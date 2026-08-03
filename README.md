# 다시, 그날 📝

> 이전의 기록을 보기 전에 기억을 먼저 떠올리고, 원본을 확인한 뒤 새롭게 떠오른 내용을 더해 하나의 추억 카드로 완성하는 회상 다이어리 서비스입니다.

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
2. **1·2차 회상과 카드 누적:** 하나의 기억은 7일 뒤와 30일 뒤 두 번 회상되며, 두 번째 회상에서 새롭게 떠오른 내용은 새 카드가 아니라 **기존 카드에 이어 붙습니다.** 회상 횟수가 아니라 원본 기억을 기준으로 카드를 관리합니다.(이때 회상 시기는 변경이 가능합니다.)
3. **동네 추억 카드:** 개인 회상 메커니즘(회상 → 원본 공개 → 새 기억 추가 → AI가 하나의 이야기로 연결)을 지역 단위로 그대로 확장했습니다. 같은 장소를 회상한 서로 다른 사용자 3명의 익명 조각이 모이면 공동체 추억 카드가 만들어져, 사라져가는 동네의 기억도 함께 보존합니다.
4. **강력한 개인정보 보호 파이프라인:** 동네 공유 전 Solar가 이름·소속·경로 등을 비식별화하고, Information Extract로 민감 후보를 한 번 더 검출한 뒤, 백엔드가 최종 결과에 남은 차단 표현을 강제로 검사합니다. 사용자는 실제로 저장될 문장을 미리 확인하고 동의해야만 공유가 진행됩니다.

**사용 언어 및 라이브러리** : Python, FastAPI, SQLAlchemy, SQLite/Supabase(Postgres), Supabase Storage, Upstage(Solar LLM·Document Parse·Information Extract), Google Gemini(Nano Banana), Leaflet.js

---

# 2️⃣ 사용자(Role)

- **일반 사용자 (User)**:
  - 사진(0~1장)과 코멘트로 기억을 등록하고, 회상 시점이 되면 질문에 답하며 회상합니다.
  - 원본 공개 후 새롭게 떠오른 기억을 추가해 추억 카드를 완성하고, 카드를 보관·숨김 처리할 수 있습니다.
  - opt-in으로 동의한 경우에만 비식별화된 회상 조각을 동네 추억 카드 재료로 공유합니다.
  - 다른 사용자의 기억·카드에는 접근할 수 없습니다.
- **관리자 (Admin)**:
  - 별도 로그인(아이디/비밀번호 + JWT)을 통해서만 접근할 수 있습니다.
  - 일반 사용자는 볼 수 없는 **동네 추억 카드 삭제·복구** 권한을 가집니다.
  - 삭제된 카드는 공개 목록과 지도에서 숨겨지며, 관리자 화면에서 이야기·버전·기여 정보를 유지한 채 복구할 수 있습니다.

---

# 3️⃣ 기능

## 1. 기억 등록

- **사용자**: 일반 사용자
- **기능**: 사진 0~1장, 코멘트, 기억 날짜, 자유 입력 장소를 `multipart/form-data`로 등록합니다. 등록과 동시에 1차(7일 뒤)·2차(30일 뒤) 회상 시기를 계산해 저장합니다.(이때 회상 시기는 변경이 가능합니다)


### 1-1. 사진 속 텍스트 인식 (조건부 OCR)

- **대상 사용자**: 일반 사용자
- **기능 설명**: 영화표·영수증처럼 사진 속에 텍스트가 있을 때만 사용자가 직접 `use_ocr`을 선택합니다. 이미지가 없는데 OCR을 요청하면 400 오류로 차단합니다. Document Parse 결과는 이후 Information Extract·Solar 분석에 함께 사용됩니다.


## 2. 기억 맥락 분석

- **사용자**: 일반 사용자 (등록 직후 자동 실행)
- **기능 설명**: Information Extract가 코멘트(+OCR 결과)에서 사람·장소·활동·분위기를 사실 기반으로 구조화하고, Solar가 그 결과를 바탕으로 제목·요약·회상 단서를 생성합니다. 원문에 없는 사건·감정은 만들어내지 않습니다.


## 3. 오늘의 회상

- **사용자**: 일반 사용자
- **기능 설명**: 회상 시각이 지난 기억만 조회합니다. 원본 코멘트·이미지는 응답에 포함하지 않고, 같은 날짜에 여러 기억이 있으면 순서와 범주형 단서로만 구분합니다.


### 3-1. 회상 질문과 단계별 힌트

- **대상 사용자**: 회상을 시작한 사용자
- **기능 설명**: 넓은 개방형 질문 하나만 먼저 보여주고, `조금 더 떠올려보기`를 선택하면 감각·분위기 → 활동·장소 순으로 점점 구체적인 힌트를 엽니다. `기억이 잘 나지 않아요`를 선택해도 실패로 기록하지 않습니다.


### 3-2. 원본 공개와 추가 회상

- **대상 사용자**: 답변을 저장한 사용자
- **기능 설명**: 답변 저장 전에는 원본 공개 버튼이 비활성화됩니다. 공개 후에는 원본 사진·코멘트·날짜를 보여주고, 새롭게 떠오른 장면·감정·대화를 추가로 작성할 수 있습니다.


## 4. 추억 카드 완성

- **사용자**: 일반 사용자
- **기능 설명**: 원본 코멘트와 원본 공개 후 새롭게 떠오른 내용만 Solar가 하나의 이야기로 연결합니다. 원본 공개 전 답변(초기 답변·힌트 답변)은 사용자가 아직 원본을 보기 전에 떠올린 추측이라 실제와 다를 수 있어, 카드 이야기에는 포함하지 않습니다. 유니크 제약을 걸어 1차 회상은 카드를 새로 만들고, 2차 회상은 같은 기억의 카드를 갱신하도록 구분합니다.

### 4-1. 추억 카드 보관함

- **대상 사용자**: 카드 소유자
- **기능 설명**: 완성한 카드를 최신순으로 조회하고, 상세 화면에서 원본 사진과 1·2차 회상 타임라인을 함께 확인합니다. 카드는 숨김 처리와 복구가 가능하며, 영구 삭제와는 구분됩니다.


### 4-2. 사진 없는 카드의 AI 이미지 생성

- **대상 사용자**: 원본 사진이 없는 카드의 소유자
- **기능 설명**: 사진이 있는 카드는 원본을 그대로 쓰고 이미지 생성 버튼 자체를 숨깁니다. 사진이 없을 때만 원본 코멘트와 1·2차 회상에서 원본 공개 후 새롭게 떠오른 내용만으로 Gemini(Nano Banana)가 이미지를 생성합니다. 원본 공개 전 답변은 실제와 다른 추측일 수 있어 이미지 생성 입력에서 제외하며, 원본 사진은 절대 Google API로 전송되지 않습니다.


## 5. 동네 추억 카드

### 5-1. 공유 미리보기와 비식별화

- **대상 사용자**: 카드를 완성한 사용자 (opt-in)
- **기능 설명**: 공유 버튼을 눌러도 바로 저장하지 않습니다. Solar가 이름·소속·경로 등을 제거한 뒤, 원본 공개 전/후 회상을 하나로 합친 요약 문장 한 개를 유효한 서버 서명과 함께 보여주고, 사용자가 최종 확인해야 실제로 저장됩니다.


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

# 4️⃣ 팀원 및 역할

| 팀원 | 주요 역할 |
| --- | --- |
| 이학진 (팀장) | 백엔드·DB 골격 설계, 회상 다이어리·동네 지도 UI 구현, 동네 카드 삭제·복구 및 재생성 기능 및 각종 버그 수정|
| 김동현 (팀원) | 타임존·지도 버벅임 버그 수정, 회상 전 추측 데이터가 카드에 섞이지 않도록 수정, 홈 화면 문구 정리 및 각종 버그 수정|
| 김진우 (팀원) | 동네 카드 자동 생성·공유 충돌 처리, 관리자·일반사용자 로그인/로그아웃 UI, README 등 문서 정리 및 각종 버그 수정 |

---

# 5️⃣ 로컬 실행 가이드

1. Python 3.11 이상 가상환경을 만들고 의존성을 설치합니다. (현재 로컬·배포 환경은 Python 3.12로 검증했습니다.)

    ```bash
    python3.12 -m venv .venv
    source .venv/bin/activate      # Windows: .venv\Scripts\activate
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

    - 데모 UI: [http://127.0.0.1:8000/demo/](http://127.0.0.1:8000/demo/) — 처음에는 개인 데이터가 로드되지 않습니다. 상단 `사용자 로그인`에 `user1`처럼 원하는 아이디를 넣고 로그인하면 해당 사용자의 기록만 불러오며, 새로고침해도 로그인 상태가 유지됩니다. 실제 신원을 검증하는 계정 기능은 아닙니다.
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
    python -m pytest         # 48개 테스트, mock AI·SQLite·로컬 Storage로 격리 실행
    python scripts/smoke_test.py   # 서버가 실행 중이어야 합니다
    ```

---

# 6️⃣ 실행 · 배포 환경 정보

현재 `main` 브랜치를 Railway에 연결해 평가용 서비스를 실제 운영하고 있습니다. 2026년 8월 3일 기준으로 서버 상태, Upstage API, Supabase Database·Storage, 기억 등록부터 2차 회상과 카드 생성, 익명 공유, Gemini 이미지 생성, 관리자 인증까지 통합 검증했습니다.

- **평가용 서비스:** [https://ai-builder-sprint-production-edfe.up.railway.app/demo/](https://ai-builder-sprint-production-edfe.up.railway.app/demo/)
- **서버 상태 확인:** [https://ai-builder-sprint-production-edfe.up.railway.app/health](https://ai-builder-sprint-production-edfe.up.railway.app/health)
- **API 문서:** [https://ai-builder-sprint-production-edfe.up.railway.app/docs](https://ai-builder-sprint-production-edfe.up.railway.app/docs)

처음 접속하면 개인 데이터는 불러오지 않습니다. 상단에서 원하는 평가용 사용자 ID를 입력하고 `로그인`을 눌러야 기억 등록·회상·개인 카드 기능이 활성화됩니다. 이 방식은 평가용 사용자를 구분하기 위한 데모 세션이며 실제 신원 인증은 아닙니다. 동네 추억 카드와 부산 기억 지도는 로그인 없이 조회할 수 있습니다.

### 심사용 접속 안내

- **일반 사용자:** 별도의 회원가입이나 비밀번호가 없습니다. 첫 화면의 `사용자 로그인`에 다른 사람과 겹치지 않는 임의의 ID(예: `judge-01`)를 입력하면 새 평가용 공간이 열립니다. 사용자 ID는 실제 인증 계정이 아니라 데모 데이터를 구분하기 위한 값이므로 개인정보를 입력하지 마세요.
- **즉시 회상 테스트:** 기억 등록 화면에서 `회상 가능일 직접 설정`을 열고 1차·2차 회상 가능일을 각각 `0일`로 설정하면 등록 직후 두 회상과 카드 갱신 흐름을 연속으로 확인할 수 있습니다.
- **공개 기능:** 동네 추억 카드와 부산 기억 지도는 로그인하지 않아도 조회할 수 있습니다.
- **관리자 기능:** 동네 카드 삭제·복구는 관리자 전용입니다. 관리자 비밀번호는 공개 저장소에 기록하지 않으며, 심사위원의 직접 테스트가 필요할 경우 제출 폼의 비공개 안내란을 통해 별도로 제공합니다.

| 구분 | 로컬 개발 | Railway 평가 배포 |
| --- | --- | --- |
| 소스·배포 | 로컬 Git checkout | GitHub `main` 브랜치가 Railway 서비스에 연결되어 merge 후 자동 배포 |
| 실행 방식 | `python run.py` (`uvicorn` reload) | `Dockerfile`의 `uvicorn app.main:app --host 0.0.0.0 --port 8000` (`PORT=8000`) |
| 실행 환경 | `ENVIRONMENT=development`, Python 3.12 | `ENVIRONMENT=production`, Railway Docker 빌드, Python 3.12 |
| 데이터베이스 | SQLite (`sqlite:///./data/memory_recall.db`), 필요 시 테이블 자동 생성 | Supabase PostgreSQL Transaction Pooler(`:6543`), `AUTO_CREATE_TABLES=false`, `sql/supabase_schema.sql` 및 `sql/migrations/`로 스키마 관리 |
| 이미지 저장 | `STORAGE_BACKEND=local`, `./data/uploads` | `STORAGE_BACKEND=supabase`, 비공개 `memory-images` 버킷 |
| AI 처리 | `AI_MODE=mock`, 외부 호출 없이 기능 흐름 검증 | `AI_MODE=upstage`, `AI_FALLBACK_TO_MOCK=false`; Solar·Document Parse·Information Extract 실제 호출 |
| 카드 이미지 | `CARD_IMAGE_MODE=mock` | `CARD_IMAGE_MODE=gemini`; 사진이 없는 개인 카드에만 Gemini 기반 이미지 생성 |
| 사용자 구분 | `AUTH_MODE=header`; 명시적 로그인 이후 `X-User-Id` 전송 | `AUTH_MODE=header`; 로그인 전 개인 API는 `401`, 공개 동네 아카이브는 로그인 없이 조회 가능 |
| 관리자 | `.env`에 관리자 계정·JWT 서명값 설정 | Railway Variables의 관리자 계정·JWT 서명값으로 로그인하며 동네 카드 삭제·복구 권한 제공 |
| 상태 점검 | `/health`, `/docs`, `python scripts/smoke_test.py` | Railway Healthcheck Path `/health`; 공개 도메인에서 HTTP 200 및 통합 흐름 확인 |

### Railway 재배포 절차

1. 변경 사항을 작업 브랜치에서 `main`으로 merge합니다.
2. Railway 서비스의 Source branch가 `main`인지 확인합니다.
3. Railway가 최신 commit으로 자동 배포하는지 `Deployments`에서 확인합니다. 자동 배포가 시작되지 않으면 `Deploy Latest Commit`을 실행합니다.
4. 배포가 `Deployment successful`이 되면 `/health`에서 `environment=production`, `ai_mode=upstage`, `storage_backend=supabase`인지 확인합니다.
5. 시크릿 창에서 `/demo/`를 열어 로그인 전 개인 데이터가 보이지 않는지 확인하고, 별도 평가용 사용자 ID로 전체 흐름을 테스트합니다.

Railway에는 `.env` 파일을 업로드하지 않고 `Variables` 탭에 환경변수를 각각 등록합니다. API 키, Supabase service role key, DB 비밀번호, 관리자 비밀번호와 서명 비밀값은 저장소에 커밋하지 않습니다. 배포에 필요한 변수 이름과 의미는 아래 `환경변수 정보` 표와 `.env.example`에서 확인할 수 있습니다.

관리자 계정, 회상 데모 압축 모드 등 시나리오별 실행 팁은 [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)에, 자동/수동 검증 기록은 [`VALIDATION.md`](VALIDATION.md)에 자세히 정리되어 있습니다.

여러 개발자가 동일한 Supabase 프로젝트에 접속할 때 Session Pooler(`:5432`)의 연결 한도를 소진하지 않도록, Pooler URL에서는 요청 종료 시 DB 연결을 즉시 반환합니다. Railway 배포에는 Transaction Pooler(`:6543`)를 사용하며, 코드는 해당 URL에서 psycopg prepared statement를 자동으로 비활성화합니다.

---

# 7️⃣ 환경변수 정보

`.env.example`을 복사해 값을 채웁니다. **`.env`는 `.gitignore`에 포함되어 있어 커밋되지 않습니다.**

| 분류 | 변수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| 기본 실행 | `ENVIRONMENT` | `development` | `production`이 아니면 `/demo` 정적 파일에 no-cache 헤더를 강제합니다. |
| | `DEBUG` | `false` | 디버그 로깅 여부. |
| | `DATABASE_URL` | `sqlite:///./data/memory_recall.db` | SQLite 또는 Supabase Postgres 연결 문자열. |
| | `AUTO_CREATE_TABLES` | `true` | 서버 시작 시 SQLAlchemy 테이블을 자동 생성할지 여부. **주의**: 없는 테이블만 새로 만들 뿐, 이미 있는 테이블에 컬럼을 추가하는 마이그레이션은 하지 않습니다. 팀원이 스키마를 바꾼 커밋을 받은 뒤에는 서버 재시작만으로 반영되지 않고, 로컬 SQLite 파일(`data/memory_recall.db`)을 지우고 다시 생성하거나 `sql/migrations/`의 해당 마이그레이션을 직접 적용해야 합니다. |
| 인증 | `AUTH_MODE` | `header` | `demo` \| `header` \| `supabase`. `header`는 개인 요청에 `X-User-Id`가 필요하며, 빈 사용자가 `demo-user`로 자동 연결되는 문제를 방지합니다. |
| | `DEMO_USER_ID` | `demo-user` | `AUTH_MODE=demo`를 명시적으로 선택했을 때만 사용하는 기본 아이디. 일반 실행과 평가용 배포에서는 사용하지 않습니다. |
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

# 개발 과정에서의 AI 협업

팀은 ChatGPT와 Codex를 단순 코드 생성기가 아니라 기획·구현·검증을 함께 수행하는 개발 보조 도구로 활용했습니다.

- **기획과 요구사항 구체화:** 인간다움이라는 주제를 회상 우선 경험, 기억 하나당 카드 하나, 동네 기억 보존이라는 구체적인 정책과 사용자 흐름으로 정리했습니다.
- **구현과 리팩터링:** FastAPI API, Supabase Database·Storage 연동, Upstage 3종 API, 반응형 프런트엔드 모듈화의 초안 작성과 코드 정리에 활용했습니다.
- **오류 분석:** Python 버전·환경변수 파싱·DB 연결·Upstage 요청 계약·탭 상태 유지·중복 카드처럼 실제 로그에서 확인된 문제의 원인을 찾고 수정안을 검토했습니다.
- **안전 정책 검토:** 원본 공개 전 추측을 카드의 사실로 사용하지 않는 규칙, 익명 공유 비식별화, 동일 사용자 중복 기여 방지, 개인 기억 삭제와 동네 카드 보존 정책의 예외 상황을 점검했습니다.
- **테스트와 배포 검증:** 자동 테스트 사례 작성, Railway 운영 서비스의 브라우저 흐름 점검, 공개·개인 API 권한 확인, Upstage·Supabase·Gemini 통합 테스트에 활용했습니다.
- **협업과 제출 준비:** GitHub 연동 기능으로 변경 범위를 확인하고 커밋·PR을 작성했으며, 브라우저 점검 기능으로 배포 화면과 실제 동작을 확인했습니다.

AI가 제안한 결과는 그대로 채택하지 않고 팀원이 코드와 정책을 검토한 뒤 자동 테스트 48개, 운영 통합 테스트, PR 단위 리뷰를 통과한 내용만 반영했습니다. 공개 가능한 실행 설정은 [`.claude/launch.json`](.claude/launch.json)에 포함했으며, API 키·DB 비밀번호·관리자 비밀번호 등 민감정보는 `.env`와 배포 환경변수로만 관리합니다.

---

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

## 7. 심사용 배포 서비스 확인 절차

심사위원은 별도의 API 키나 로컬 환경 설정 없이 Railway 평가용 웹사이트에서 핵심 흐름을 확인할 수 있다.

1. [평가용 서비스](https://ai-builder-sprint-production-edfe.up.railway.app/demo/)에 접속한다.
2. 상단 `사용자 로그인`에 다른 사람과 겹치지 않는 임의의 ID(예: `judge-01`)를 입력한다. 실제 인증 계정이 아니므로 개인정보는 입력하지 않는다.
3. 티켓·영수증처럼 글자가 있는 사진과 코멘트를 등록하고 `사진 속 글자도 기억에 활용하기`를 선택한다.
4. 전체 흐름을 즉시 확인하려면 `회상 가능일 직접 설정`에서 1차·2차 회상을 각각 `0일`로 설정한 뒤 기억을 맡긴다.
5. AI 맥락 정리가 끝나면 `오늘의 회상`에서 Solar가 생성한 개방형 질문과 단계별 힌트를 확인하고 답변을 저장한다.
6. 그날의 원본을 확인하고 새롭게 떠오른 내용을 더해 개인 추억 카드를 완성한다. 두 번째 회상은 새 카드를 만들지 않고 기존 카드에 이어 붙는다.
7. 개인 카드의 `동네에 익명 공유`에서 실제 저장 전에 이름·소속·구체적 경로 등이 일반화된 미리보기를 확인한다.
8. `동네 추억 카드`에서 미리 구성된 공개 카드와 부산 기억 지도를 확인한다. 서로 다른 사용자 3명의 자동 생성 과정과 관리자 기능은 제출 데모 영상으로도 확인할 수 있다.
9. [서버 상태](https://ai-builder-sprint-production-edfe.up.railway.app/health)에서 `environment: production`, `ai_mode: upstage`, `storage_backend: supabase`를 확인한다.

관리자 삭제·복구 기능을 심사위원이 직접 시험해야 하는 경우 관리자 자격 증명은 공개 저장소가 아니라 제출 폼의 비공개 안내를 통해 제공한다.

---

## 8. 개발자용 로컬·API 재현 절차

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


## 9. 보조 AI: 추억 카드 이미지 생성

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

## 10. 한 문장 정리

> Document Parse가 사진 속 기록을 읽고, Information Extract가 기억의 사실을 구조화하며, Solar LLM이 그 사실을 벗어나지 않는 질문과 이야기를 생성해 사용자가 스스로 기억을 되살리도록 돕는다.
