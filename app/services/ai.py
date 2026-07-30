from __future__ import annotations

import base64
import io
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, TypeVar

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.errors import ServiceError

logger = logging.getLogger(__name__)
T = TypeVar("T")


EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "people": {
            "type": "array",
            "items": {"type": "string"},
            "description": "원문에 직접 등장하는 사람 이름 또는 관계만 추출",
        },
        "places": {
            "type": "array",
            "items": {"type": "string"},
            "description": "원문에 직접 등장하는 장소만 추출",
        },
        "activities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "원문에 직접 등장하는 행동이나 활동만 추출",
        },
        "atmosphere": {
            "type": "array",
            "items": {"type": "string"},
            "description": "날씨, 시간대, 주변 환경처럼 원문에 직접 표현된 분위기만 추출",
        },
        "emotions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "사용자가 원문에서 직접 표현한 감정만 추출. 추론하지 않음",
        },
    },
    "required": ["people", "places", "activities", "atmosphere", "emotions"],
    "additionalProperties": False,
}


class MockAI:
    def __init__(self, settings: Settings):
        self.settings = settings

    def parse_document(self, *, data: bytes, filename: str, content_type: str) -> str:
        lower = filename.lower()
        if any(keyword in lower for keyword in ["ticket", "movie", "영화", "티켓"]):
            return "영화 관람권\n2026년 7월 20일 19:30\n부산 센텀시티"
        if any(keyword in lower for keyword in ["receipt", "영수증", "menu", "메뉴"]):
            return "광안리 바다횟집\n모둠회 1\n결제 시각 20:18"
        if any(keyword in lower for keyword in ["letter", "편지", "memo", "메모"]):
            return "오늘의 기억을 오래 간직하자."
        return ""

    def extract_context(self, *, text: str) -> dict[str, list[str]]:
        people: list[str] = []
        places: list[str] = []
        activities: list[str] = []
        atmosphere: list[str] = []
        emotions: list[str] = []

        for tag in self.settings.place_tags:
            if tag in text and tag not in places:
                places.append(tag)

        generic_places = ["바닷가", "바다", "카페", "학교", "공원", "영화관", "식당", "집", "시장"]
        for word in generic_places:
            if word in text and word not in places:
                places.append(word)

        person_patterns = [
            r"([가-힣]{2,4})(?:와|과|랑|이랑)\s",
            r"친구\s*([가-힣]{2,4})",
        ]
        for pattern in person_patterns:
            for match in re.findall(pattern, text):
                if match not in {"친구", "함께", "바다"} and match not in people:
                    people.append(match)

        activity_map = {
            "먹": "식사",
            "회": "회 먹기",
            "산책": "산책",
            "걷": "걷기",
            "영화": "영화 보기",
            "공연": "공연 관람",
            "수영": "수영",
            "사진": "사진 찍기",
            "여행": "여행",
            "데이트": "데이트",
            "커피": "커피 마시기",
        }
        for keyword, label in activity_map.items():
            if keyword in text and label not in activities:
                activities.append(label)

        atmosphere_map = {
            "비": "비 오는 날",
            "눈": "눈 오는 날",
            "맑": "맑은 날",
            "밤": "밤",
            "저녁": "저녁",
            "노을": "노을",
            "바람": "바람",
            "조용": "조용한 분위기",
            "북적": "북적이는 분위기",
            "바다": "바다",
        }
        for keyword, label in atmosphere_map.items():
            if keyword in text and label not in atmosphere:
                atmosphere.append(label)

        emotion_map = {
            "행복": "행복",
            "즐거": "즐거움",
            "설렜": "설렘",
            "설레": "설렘",
            "슬펐": "슬픔",
            "아쉬": "아쉬움",
            "그리": "그리움",
            "긴장": "긴장",
        }
        for keyword, label in emotion_map.items():
            if keyword in text and label not in emotions:
                emotions.append(label)

        return {
            "people": people,
            "places": places,
            "activities": activities,
            "atmosphere": atmosphere,
            "emotions": emotions,
        }

    def analyze_memory(self, *, original_text: str, extracted: dict[str, Any]) -> dict[str, Any]:
        place = next(iter(extracted.get("places") or []), None)
        atmosphere = next(iter(extracted.get("atmosphere") or []), None)
        people = extracted.get("people") or []
        activities = extracted.get("activities") or []

        if place and atmosphere:
            title = f"{atmosphere}의 {place}"
        elif place:
            title = f"{place}에서의 하루"
        else:
            title = "다시 떠올릴 하루"

        summary_parts: list[str] = []
        if people:
            summary_parts.append(f"{', '.join(people)}와 함께")
        if place:
            summary_parts.append(f"{place}에서")
        if activities:
            summary_parts.append(f"{', '.join(activities)}를 했던 기억")
        summary = " ".join(summary_parts).strip() or original_text.strip().replace("\n", " ")[:120]

        cues: list[str] = []
        cue_map = [
            ("people", "함께한 사람"),
            ("places", "그날의 장소와 주변 풍경"),
            ("activities", "그날 했던 행동"),
            ("atmosphere", "날씨와 주변 분위기"),
            ("emotions", "그때 직접 표현한 감정"),
        ]
        for key, cue in cue_map:
            if extracted.get(key):
                cues.append(cue)
        if not cues:
            cues = ["함께한 사람", "머물렀던 장소", "그날 했던 일"]

        return {
            "title": title,
            "summary": summary,
            "emotions": extracted.get("emotions") or [],
            "recall_cues": cues[:4],
        }

    def generate_questions(self, *, extracted: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
        questions = [
            {"level": 1, "question": "그날 누구와 어떤 시간을 보냈는지 자유롭게 떠올려보세요."},
            {"level": 2, "question": "머물렀던 장소의 풍경이나 주변 분위기는 어땠나요?"},
            {"level": 3, "question": "그날 함께 먹거나 걷거나 나누었던 행동이 기억나나요?"},
        ]
        if extracted.get("people"):
            questions[0] = {"level": 1, "question": "그날 함께한 사람이 있었나요? 어떤 시간을 보냈는지 떠올려보세요."}
        if extracted.get("atmosphere"):
            questions[1] = {"level": 2, "question": "그날의 날씨와 주변 분위기를 천천히 떠올려보세요."}
        return questions

    def create_memory_card(
        self,
        *,
        original_comment: str,
        memory_date: str,
        analysis: dict[str, Any],
        initial_answer: str,
        hint_answers: list[dict[str, Any]],
        newly_recalled_text: str,
    ) -> dict[str, Any]:
        title = analysis.get("title") or "다시 이어진 기억"
        pre = initial_answer.strip() if initial_answer else "처음에는 선명한 장면을 떠올리기 어려웠다."
        post = newly_recalled_text.strip()
        story = f"{original_comment.strip()} 원본을 보기 전에는 {pre}"
        if post:
            story += f" 사진을 확인한 뒤에는 {post}라는 장면이 새롭게 이어졌다."
        else:
            story += " 사진을 확인하며 그날의 장면을 다시 마주했다."
        details = [piece.strip() for piece in re.split(r"[.!?\n]+", post) if piece.strip()][:5]
        return {
            "card_title": title,
            "story": story,
            "reflection": "기억의 정확도를 가르는 대신, 떠올린 조각과 다시 만난 장면을 하나의 추억으로 이어 보았어요.",
            "newly_recalled_details": details,
        }

    def prepare_town_fragments(self, *, place_tag: str, fragments: list[dict[str, str]]) -> dict[str, Any]:
        documents = [" ".join(filter(None, [item.get("pre_reveal_text", ""), item.get("post_reveal_text", "")])) for item in fragments]
        theme_keywords = {
            "바다 풍경": ["바다", "해변", "해수욕장", "파도"],
            "함께한 만남": ["친구", "가족", "함께", "만남"],
            "걷기": ["걷", "산책"],
            "음악": ["음악", "노래", "버스킹"],
            "사진": ["사진", "출사"],
            "식사": ["먹", "식사", "회", "초밥"],
            "비 오는 날": ["비", "우산"],
        }
        shared_themes = []
        for theme, keywords in theme_keywords.items():
            if sum(any(keyword in document for keyword in keywords) for document in documents) >= 2:
                shared_themes.append(theme)

        blocked_terms: list[str] = []
        for document in documents:
            blocked_terms.extend(self.extract_context(text=document).get("people", []))
            blocked_terms.extend(re.findall(r"[가-힣A-Za-z0-9]+\s*(?:동아리|모임|학회|총사)", document))
        blocked_terms = [term for term in dict.fromkeys(blocked_terms) if term and term != place_tag]
        safe_themes = shared_themes[:5] or ["서로 다른 만남과 일상의 장면"]
        return {
            "safe_fragments": [{"text": theme} for theme in safe_themes],
            "common_themes": safe_themes,
            "blocked_terms": blocked_terms,
        }

    def sanitize_town_contribution(self, *, place_tag: str, pre_text: str, post_text: str) -> dict[str, Any]:
        """Mock 모드에서도 개인 원문 대신 넓은 범주의 회상 조각만 저장한다."""
        combined = " ".join(filter(None, [pre_text, post_text]))
        extracted = self.extract_context(text=combined)
        activities = extracted.get("activities", [])[:3]
        atmosphere = extracted.get("atmosphere", [])[:3]
        safe_parts = [*activities, *atmosphere]
        safe_text = ", ".join(dict.fromkeys(safe_parts)) or "함께한 시간과 장소의 분위기를 떠올린 기억"
        blocked_terms = [
            *extracted.get("people", []),
            *re.findall(r"[가-힣A-Za-z0-9]+\s*(?:동아리|모임|학회|총사)", combined),
        ]
        return {
            "safe_pre_text": f"{place_tag}에서 {safe_text}",
            "safe_post_text": "원본을 본 뒤 장소의 분위기와 함께한 장면을 더 떠올림" if post_text else "",
            "blocked_terms": list(dict.fromkeys(term for term in blocked_terms if term and term != place_tag)),
        }

    def create_town_card(
        self,
        *,
        place_tag: str,
        fragments: list[dict[str, str]],
        common_themes: list[str] | None = None,
        blocked_terms: list[str] | None = None,
    ) -> dict[str, Any]:
        themes = common_themes or [item.get("text", "") for item in fragments if item.get("text")]
        theme_text = ", ".join(themes) if themes else "서로 다른 만남과 일상의 장면"
        return {
            "card_title": f"여러 사람의 기억으로 다시 쓰인 {place_tag}",
            "story": f"여러 사람의 기억 속 {place_tag}에는 {theme_text}이 공통된 모습으로 남아 있다. 개인의 구체적인 사연 대신, 장소를 함께 이루는 분위기와 장면을 모았다.",
            "reflection": "개인의 세부 정보는 덜어내고, 여러 기억에 반복된 장소의 모습을 함께 남겼어요.",
        }


class UpstageAI:
    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.upstage_api_key:
            raise ServiceError("UPSTAGE_API_KEY가 설정되지 않았습니다.", status_code=500)
        self.headers = {"Authorization": f"Bearer {settings.upstage_api_key}"}

    def _post_json(self, url: str, **kwargs) -> dict[str, Any]:
        try:
            response = httpx.post(url, timeout=self.settings.upstage_timeout_seconds, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:1000]
            raise ServiceError(
                "Upstage API가 오류를 반환했습니다.",
                detail={"status_code": exc.response.status_code, "body": body},
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ServiceError("Upstage API 호출 또는 응답 해석에 실패했습니다.", detail={"error": str(exc)}) from exc

    def parse_document(self, *, data: bytes, filename: str, content_type: str) -> str:
        payload = self._post_json(
            self.settings.upstage_document_parse_url,
            headers=self.headers,
            files={"document": (filename, data, content_type)},
            data={"model": self.settings.upstage_document_parse_model},
        )
        candidates = [
            payload.get("text"),
            payload.get("content", {}).get("text") if isinstance(payload.get("content"), dict) else None,
            payload.get("content", {}).get("html") if isinstance(payload.get("content"), dict) else None,
            payload.get("html"),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return self._strip_html(candidate)
        pages = payload.get("pages")
        if isinstance(pages, list):
            texts = []
            for page in pages:
                if isinstance(page, dict):
                    for key in ("text", "content", "html"):
                        value = page.get(key)
                        if isinstance(value, str) and value.strip():
                            texts.append(self._strip_html(value))
                            break
            if texts:
                return "\n".join(texts)
        raise ServiceError("Document Parse 응답에서 텍스트를 찾지 못했습니다.", detail={"keys": list(payload.keys())})

    def extract_context(self, *, text: str) -> dict[str, list[str]]:
        """Extract facts from comment + OCR text with Upstage Information Extraction.

        The current Information Extraction endpoint accepts a document/image through an
        ``image_url`` message and a JSON schema response format. Because this service also
        supports memories without an original photo, the source text is rendered to a PNG
        document first. This keeps the product contract (comment + optional OCR text) the
        same for both photo and text-only memories.
        """
        document_png = self._render_text_document(text)
        data_url = "data:image/png;base64," + base64.b64encode(document_png).decode("ascii")
        body = {
            "model": self.settings.upstage_information_extract_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        }
                    ],
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "memory_context",
                    "schema": EXTRACT_SCHEMA,
                },
            },
        }
        payload = self._post_json(
            self.settings.upstage_information_extract_url,
            headers={**self.headers, "Content-Type": "application/json"},
            json=body,
        )
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ServiceError(
                "Information Extract 응답에서 구조화 내용을 찾지 못했습니다.",
                detail={"keys": list(payload.keys()) if isinstance(payload, dict) else []},
            ) from exc
        candidate = self._parse_json_text(content)
        return self._normalize_extracted(candidate)

    def _render_text_document(self, text: str) -> bytes:
        cleaned = text.strip()
        if not cleaned:
            cleaned = "기록된 텍스트 없음"

        font_path = self._find_text_render_font()
        try:
            font = ImageFont.truetype(str(font_path), size=30)
            title_font = ImageFont.truetype(str(font_path), size=34)
        except OSError as exc:
            raise ServiceError(
                "Information Extract용 한글 문서 이미지를 만들 글꼴을 열 수 없습니다.",
                detail={"font_path": str(font_path)},
            ) from exc

        width = 1400
        margin = 72
        line_gap = 16
        max_text_width = width - margin * 2
        lines = self._wrap_text(cleaned, font, max_text_width)
        title = "기억 원문 (사용자 코멘트 + 사진 속 텍스트)"
        line_height = max(44, font.getbbox("가Ag")[3] - font.getbbox("가Ag")[1] + line_gap)
        title_height = 72
        height = max(500, margin * 2 + title_height + line_height * max(1, len(lines)))
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        draw.text((margin, margin), title, font=title_font, fill="black")
        y = margin + title_height
        for line in lines:
            draw.text((margin, y), line, font=font, fill="black")
            y += line_height

        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()

    def _find_text_render_font(self) -> Path:
        configured = self.settings.upstage_text_render_font_path
        candidates = [
            configured,
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
            "C:/Windows/Fonts/malgun.ttf",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return Path(candidate)
        raise ServiceError(
            "Information Extract용 한글 글꼴을 찾지 못했습니다.",
            detail={
                "hint": "UPSTAGE_TEXT_RENDER_FONT_PATH에 한글 TrueType/OpenType 글꼴 경로를 지정하세요."
            },
        )

    @staticmethod
    def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
        lines: list[str] = []
        for paragraph in text.splitlines() or [text]:
            if not paragraph:
                lines.append("")
                continue
            current = ""
            for token in re.findall(r"\S+|\s+", paragraph):
                candidate = current + token
                bbox = font.getbbox(candidate)
                if current and bbox[2] - bbox[0] > max_width:
                    lines.append(current.rstrip())
                    current = token.lstrip()
                else:
                    current = candidate
            if current or not lines:
                lines.append(current.rstrip())
        return lines

    def analyze_memory(self, *, original_text: str, extracted: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
다음은 사용자가 직접 남긴 기억 원문과 사실 기반 추출 결과입니다.
기억을 채점하지 말고, 원문에 없는 사건·감정·인물을 만들지 마세요.
반드시 JSON 객체만 반환하세요.

원문:
{original_text}

추출 결과:
{json.dumps(extracted, ensure_ascii=False)}

출력 스키마:
{{
  "title": "짧고 자연스러운 제목",
  "summary": "사실만 사용한 한 문장 요약",
  "emotions": ["원문에 명시된 감정만"],
  "recall_cues": ["정답을 직접 말하지 않는 회상 단서 3~4개"]
}}
""".strip()
        return self._solar_json(prompt)

    def generate_questions(self, *, extracted: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
        prompt = f"""
사용자가 원본 사진과 코멘트를 보기 전에 기억을 자유롭게 떠올리도록 돕는 질문과 단계별 힌트를 만드세요.
정답을 직접 노출하거나 맞히기 문제처럼 만들지 마세요. 사용자가 틀렸다는 느낌을 주지 마세요.
level 1은 넓은 개방형 질문, level 2는 감각·분위기 중심의 약한 힌트, level 3은 활동·장소 범주의 조금 더 구체적인 힌트로 작성하세요.
사람 이름, 정확한 가게명, 음식명처럼 사실상 정답이 되는 정보는 힌트에서도 직접 밝히지 말고, 원본에 없는 내용을 만들지 마세요.
반드시 JSON 객체만 반환하세요.

사실 기반 맥락:
{json.dumps(extracted, ensure_ascii=False)}

분석:
{json.dumps(analysis, ensure_ascii=False)}

출력:
{{"questions":[
  {{"level":1,"question":"..."}},
  {{"level":2,"question":"..."}},
  {{"level":3,"question":"..."}}
]}}
""".strip()
        result = self._solar_json(prompt)
        questions = result.get("questions")
        if not isinstance(questions, list):
            raise ServiceError("Solar 질문 생성 응답에 questions 배열이 없습니다.")
        return questions

    def create_memory_card(
        self,
        *,
        original_comment: str,
        memory_date: str,
        analysis: dict[str, Any],
        initial_answer: str,
        hint_answers: list[dict[str, Any]],
        newly_recalled_text: str,
    ) -> dict[str, Any]:
        prompt = f"""
다음 기록을 하나의 추억 카드로 자연스럽게 연결하세요.
사용자의 회상 정확도를 평가하거나 정답률을 언급하지 마세요.
원본과 사용자 답변에 없는 사건을 추가하지 마세요.
회상 전 내용과 원본 공개 후 새롭게 떠오른 내용을 구분해 이야기 속에서 연결하세요.
반드시 JSON 객체만 반환하세요.

기억 날짜: {memory_date}
원본 코멘트: {original_comment}
등록 당시 분석: {json.dumps(analysis, ensure_ascii=False)}
원본 공개 전 답변: {initial_answer}
힌트 이후 답변: {json.dumps(hint_answers, ensure_ascii=False)}
원본 공개 후 새롭게 떠오른 내용: {newly_recalled_text}

출력:
{{
  "card_title":"...",
  "story":"...",
  "reflection":"채점 없이 회상의 의미를 담은 짧은 문장",
  "newly_recalled_details":["사용자가 추가한 세부 내용만"]
}}
""".strip()
        return self._solar_json(prompt)

    def prepare_town_fragments(self, *, place_tag: str, fragments: list[dict[str, str]]) -> dict[str, Any]:
        prompt = f"""
다음 회상 조각을 공개 가능한 동네 아카이브 재료로 비식별화하세요.
이름·별명·소속·학교·단체·모임명·구체적인 이동 경로·정확한 시각을 제거하세요.
한 사람에게만 등장한 영화명·음식명·고유 사건 등 희귀한 세부 내용은 제외하거나 넓은 범주로 일반화하세요.
서로 다른 기여자 2명 이상에게 반복된 장소의 활동·분위기·감각만 common_themes에 포함하세요.
개인별 사건을 재구성할 수 있는 문장은 safe_fragments에 넣지 마세요.
비속어·욕설·혐오·모욕 표현은 인용하지 말고 중립적인 표현으로 바꾸거나 생략하세요.
장소 태그 '{place_tag}' 자체는 유지할 수 있습니다. 반드시 JSON 객체만 반환하세요.

회상 조각:
{json.dumps(fragments, ensure_ascii=False)}

출력:
{{
  "safe_fragments":[{{"text":"비식별화되고 일반화된 공통 장면"}}],
  "common_themes":["2명 이상에게 반복된 주제"],
  "blocked_terms":["제거한 이름·소속·고유 표현"]
}}
""".strip()
        result = self._solar_json(prompt)
        safe_fragments = result.get("safe_fragments") if isinstance(result.get("safe_fragments"), list) else []
        common_themes = result.get("common_themes") if isinstance(result.get("common_themes"), list) else []
        blocked_terms = result.get("blocked_terms") if isinstance(result.get("blocked_terms"), list) else []
        return {
            "safe_fragments": [item for item in safe_fragments if isinstance(item, dict) and str(item.get("text", "")).strip()],
            "common_themes": [str(item).strip() for item in common_themes if str(item).strip()],
            "blocked_terms": [str(item).strip() for item in blocked_terms if str(item).strip() and str(item).strip() != place_tag],
        }

    def sanitize_town_contribution(self, *, place_tag: str, pre_text: str, post_text: str) -> dict[str, Any]:
        prompt = f"""
다음 개인 회상 내용을 동네 아카이브에 저장 가능한 비식별 조각으로 바꾸세요.
이 단계의 결과는 데이터베이스에 장기 보존될 수 있으므로 원문을 복사하지 마세요.
이름·별명·소속·학교·단체·모임명·정확한 시간·구체적인 이동 경로를 제거하세요.
영화명·가게명·메뉴명·고유 사건처럼 개인을 특정할 수 있는 희귀한 세부 정보는
'문화 활동', '식사', '산책', '사람들과의 만남'처럼 넓은 범주로 일반화하세요.
장소 태그 '{place_tag}' 자체와 일반적인 분위기·감각·활동만 유지할 수 있습니다.
비속어·욕설·혐오·모욕 표현은 그대로 옮기지 말고 삭제하거나 중립적인 표현으로 일반화하세요.
새로운 사실은 만들지 말고 반드시 JSON 객체만 반환하세요.

원본 공개 전 회상: {pre_text}
원본 공개 후 회상: {post_text}

출력:
{{
  "safe_pre_text":"비식별화된 짧은 회상 조각",
  "safe_post_text":"비식별화된 추가 회상 조각 또는 빈 문자열",
  "blocked_terms":["제거한 이름·소속·고유 표현"]
}}
""".strip()
        result = self._solar_json(prompt)
        return {
            "safe_pre_text": str(result.get("safe_pre_text") or "").strip(),
            "safe_post_text": str(result.get("safe_post_text") or "").strip(),
            "blocked_terms": [
                str(item).strip() for item in result.get("blocked_terms", [])
                if str(item).strip() and str(item).strip() != place_tag
            ] if isinstance(result.get("blocked_terms"), list) else [],
        }

    def create_town_card(
        self,
        *,
        place_tag: str,
        fragments: list[dict[str, str]],
        common_themes: list[str] | None = None,
        blocked_terms: list[str] | None = None,
    ) -> dict[str, Any]:
        prompt = f"""
장소 '{place_tag}'에 대해 사전 비식별화된 공통 주제만 사용해 동네 추억 카드를 만드세요.
개인별 기억을 나열하거나 인물·소속·이동 경로·희귀한 사건을 복원하지 마세요.
blocked_terms의 표현은 어떤 형태로도 출력하지 마세요.
비속어·욕설·혐오·모욕 표현은 인용하지 말고 중립적인 표현으로 바꾸거나 생략하세요.
여러 기여자에게 반복된 장소의 분위기와 활동만 공동체 수준으로 서술하세요.
역사적 사실이나 제공되지 않은 내용을 추가하지 마세요.
반드시 JSON 객체만 반환하세요.

비식별화된 공통 조각:
{json.dumps(fragments, ensure_ascii=False)}
공통 주제:
{json.dumps(common_themes or [], ensure_ascii=False)}
출력 금지 표현:
{json.dumps(blocked_terms or [], ensure_ascii=False)}

출력:
{{
  "card_title":"...",
  "story":"...",
  "reflection":"..."
}}
""".strip()
        return self._solar_json(prompt)

    def _solar_json(self, prompt: str) -> dict[str, Any]:
        url = f"{self.settings.upstage_base_url.rstrip('/')}/chat/completions"
        body = {
            "model": self.settings.upstage_solar_model,
            "messages": [
                {"role": "system", "content": "당신은 사용자의 기억을 채점하지 않고 회상을 돕는 한국어 기록 도우미입니다."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            payload = self._post_json(url, headers={**self.headers, "Content-Type": "application/json"}, json=body)
        except ServiceError as first_error:
            body.pop("response_format", None)
            try:
                payload = self._post_json(url, headers={**self.headers, "Content-Type": "application/json"}, json=body)
            except ServiceError:
                raise first_error
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ServiceError("Solar 응답에서 메시지 내용을 찾지 못했습니다.") from exc
        return self._parse_json_text(content)

    @staticmethod
    def _parse_json_text(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                try:
                    value = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    raise ServiceError("Solar JSON 응답을 해석하지 못했습니다.", detail={"content": text[:1000]}) from exc
            else:
                raise ServiceError("Solar JSON 응답을 해석하지 못했습니다.", detail={"content": text[:1000]}) from exc
        if not isinstance(value, dict):
            raise ServiceError("Solar 응답은 JSON 객체여야 합니다.")
        return value

    @staticmethod
    def _strip_html(value: str) -> str:
        return re.sub(r"<[^>]+>", " ", value).replace("&nbsp;", " ").strip()

    @staticmethod
    def _normalize_extracted(value: dict[str, Any]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for key in EXTRACT_SCHEMA["properties"]:
            raw = value.get(key, [])
            if isinstance(raw, dict) and "value" in raw:
                raw = raw["value"]
            if raw is None:
                items = []
            elif isinstance(raw, list):
                items = [str(item).strip() for item in raw if str(item).strip()]
            else:
                items = [str(raw).strip()] if str(raw).strip() else []
            result[key] = list(dict.fromkeys(items))
        return result


class AIService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.mock = MockAI(settings)
        self.upstage = UpstageAI(settings) if settings.upstage_api_key else None

    def _execute(self, upstage_call: Callable[[], T], mock_call: Callable[[], T]) -> T:
        if self.settings.ai_mode == "mock":
            return mock_call()
        if self.upstage is None:
            if self.settings.ai_mode == "auto":
                return mock_call()
            raise ServiceError("UPSTAGE_API_KEY가 설정되지 않았습니다.", status_code=500)
        try:
            return upstage_call()
        except ServiceError:
            if self.settings.ai_mode == "auto" and self.settings.ai_fallback_to_mock:
                logger.exception("Upstage 호출 실패로 mock 결과를 사용합니다.")
                return mock_call()
            raise

    def parse_document(self, **kwargs) -> str:
        return self._execute(
            lambda: self.upstage.parse_document(**kwargs),
            lambda: self.mock.parse_document(**kwargs),
        )

    def extract_context(self, **kwargs) -> dict[str, list[str]]:
        return self._execute(
            lambda: self.upstage.extract_context(**kwargs),
            lambda: self.mock.extract_context(**kwargs),
        )

    def analyze_memory(self, **kwargs) -> dict[str, Any]:
        return self._execute(
            lambda: self.upstage.analyze_memory(**kwargs),
            lambda: self.mock.analyze_memory(**kwargs),
        )

    def generate_questions(self, **kwargs) -> list[dict[str, Any]]:
        return self._execute(
            lambda: self.upstage.generate_questions(**kwargs),
            lambda: self.mock.generate_questions(**kwargs),
        )

    def create_memory_card(self, **kwargs) -> dict[str, Any]:
        return self._execute(
            lambda: self.upstage.create_memory_card(**kwargs),
            lambda: self.mock.create_memory_card(**kwargs),
        )

    def prepare_town_fragments(self, **kwargs) -> dict[str, Any]:
        return self._execute(
            lambda: self.upstage.prepare_town_fragments(**kwargs),
            lambda: self.mock.prepare_town_fragments(**kwargs),
        )

    def sanitize_town_contribution(self, **kwargs) -> dict[str, Any]:
        return self._execute(
            lambda: self.upstage.sanitize_town_contribution(**kwargs),
            lambda: self.mock.sanitize_town_contribution(**kwargs),
        )

    def create_town_card(self, **kwargs) -> dict[str, Any]:
        return self._execute(
            lambda: self.upstage.create_town_card(**kwargs),
            lambda: self.mock.create_town_card(**kwargs),
        )
