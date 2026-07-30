from __future__ import annotations

import base64
import hashlib
import io
from typing import Any

import httpx
from PIL import Image, ImageDraw

from app.config import Settings
from app.errors import ServiceError


class CardImageService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def build_prompt(
        self,
        *,
        mode: str,
        style: str,
        memory_date: str,
        place: str | None,
        story: str,
        details: list[str],
    ) -> str:
        style_copy = {
            "warm_watercolor": "따뜻하고 차분한 수채화 회상 다이어리",
            "soft_film": "부드러운 필름 색감의 손그림 일러스트",
            "paper_collage": "질감이 은은한 종이 콜라주 일러스트",
        }.get(style, "따뜻하고 차분한 수채화 회상 다이어리")
        source_rule = (
            "첨부된 사진의 구도와 주요 사물 배치를 유지하고, 사진에 없는 사람·사건·물건을 추가하지 마세요. "
            if mode == "photo_illustration"
            else "아래 기록에 명시되지 않은 사람·사건·물건을 추가하지 말고, 실제 사진처럼 위장하지 마세요. "
        )
        return (
            f"추억 카드에 사용할 {style_copy} 이미지를 만드세요. {source_rule}"
            "실존 인물을 식별할 수 있는 얼굴 대신 뒷모습이나 실루엣을 사용하세요. "
            "이름, 상호명, 학교명, 전화번호, 로고, 날짜, 문구를 이미지에 넣지 마세요. "
            "기억의 사실을 재구성하거나 과장하지 말고 상징적인 분위기만 표현하세요. 가로 4:3 비율.\n"
            f"기억 시점: {memory_date}\n장소 범주: {place or '특정하지 않음'}\n"
            f"추억 이야기: {story[:1800]}\n추가로 떠오른 조각: {', '.join(details[:5]) or '없음'}"
        )

    @staticmethod
    def choose_style(story: str) -> str:
        text = story.lower()
        if any(keyword in text for keyword in ("밤", "비", "바다", "노을", "여행")):
            return "soft_film"
        if any(keyword in text for keyword in ("가족", "친구", "함께", "웃", "대화")):
            return "warm_watercolor"
        return "paper_collage"

    def generate(
        self,
        *,
        prompt: str,
        source_image: bytes | None = None,
        source_content_type: str | None = None,
    ) -> bytes:
        if not self.settings.card_image_generation_enabled:
            raise ServiceError("추억 이미지 생성 기능이 비활성화되어 있습니다.", status_code=503)
        if self.settings.card_image_mode == "mock":
            return self._mock_image(prompt)
        try:
            generated = self._gemini_image(prompt, source_image, source_content_type)
        except ServiceError:
            if self.settings.card_image_mode == "auto":
                return self._mock_image(prompt)
            raise
        return self._normalize_png(generated)

    def _gemini_image(self, prompt: str, source_image: bytes | None, source_content_type: str | None) -> bytes:
        if not self.settings.gemini_api_key:
            raise ServiceError("GEMINI_API_KEY가 설정되지 않았습니다.", status_code=503)
        inputs: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if source_image:
            inputs.insert(0, {
                "type": "image",
                "data": base64.b64encode(source_image).decode("ascii"),
                "mime_type": source_content_type or "image/jpeg",
            })
        try:
            response = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={"x-goog-api-key": self.settings.gemini_api_key, "Content-Type": "application/json"},
                json={"model": self.settings.nano_banana_model, "input": inputs},
                timeout=self.settings.nano_banana_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            raise ServiceError("Nano Banana 이미지 생성에 실패했습니다.", detail={"status": status, "error": str(exc)}) from exc
        image_data = self._find_image_data(response.json())
        if not image_data:
            raise ServiceError("Nano Banana 응답에서 생성 이미지를 찾지 못했습니다.")
        try:
            return base64.b64decode(image_data)
        except ValueError as exc:
            raise ServiceError("Nano Banana 이미지 데이터를 해석하지 못했습니다.") from exc

    @classmethod
    def _find_image_data(cls, value: Any) -> str | None:
        if isinstance(value, dict):
            if value.get("type") == "image" and isinstance(value.get("data"), str):
                return value["data"]
            if isinstance(value.get("output_image"), dict) and isinstance(value["output_image"].get("data"), str):
                return value["output_image"]["data"]
            for child in value.values():
                found = cls._find_image_data(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = cls._find_image_data(child)
                if found:
                    return found
        return None

    @staticmethod
    def _mock_image(prompt: str) -> bytes:
        digest = hashlib.sha256(prompt.encode("utf-8")).digest()
        base = (225 + digest[0] % 20, 215 + digest[1] % 20, 195 + digest[2] % 25)
        image = Image.new("RGB", (1200, 900), base)
        draw = ImageDraw.Draw(image, "RGBA")
        colors = [(53, 92, 73, 115), (188, 112, 79, 90), (255, 253, 248, 150)]
        for index in range(12):
            x = (digest[index] / 255) * 1000
            y = (digest[index + 10] / 255) * 700
            size = 120 + digest[index + 20]
            draw.ellipse((x, y, x + size, y + size), fill=colors[index % len(colors)])
        draw.rectangle((80, 675, 1120, 820), fill=(255, 253, 248, 115))
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    @staticmethod
    def _normalize_png(data: bytes) -> bytes:
        try:
            with Image.open(io.BytesIO(data)) as image:
                normalized = image.convert("RGB")
                output = io.BytesIO()
                normalized.save(output, format="PNG", optimize=True)
                return output.getvalue()
        except (OSError, ValueError) as exc:
            raise ServiceError("Nano Banana가 유효한 이미지 파일을 반환하지 않았습니다.") from exc
