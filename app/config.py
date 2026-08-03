from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_PLACE_TAGS = [
    "감천문화마을",
    "개금",
    "경성대·부경대",
    "광안리",
    "괴정",
    "구포",
    "금정산",
    "기장",
    "남천",
    "남포동",
    "다대포",
    "대신",
    "덕천",
    "동래",
    "만덕",
    "망미",
    "명륜",
    "명지",
    "문현",
    "반송",
    "반여",
    "범일",
    "부곡",
    "부산대학교",
    "부산역",
    "사상",
    "서면",
    "센텀",
    "송도",
    "송정",
    "수영",
    "수정",
    "신평",
    "안락",
    "엄궁",
    "연산동",
    "영도",
    "온천천",
    "용호동",
    "일광",
    "장림",
    "재송",
    "전포",
    "정관",
    "좌동",
    "주례",
    "토성",
    "하단",
    "해운대",
    "화명",
]

# 사용자는 구체적인 장소를 적고, 동네 카드는 비교적 넓은 생활권으로 묶는다.
PLACE_TAG_ALIASES = {
    "광안리": ["광안리해수욕장", "민락동", "민락수변공원", "수영구"],
    "해운대": ["해운대해수욕장", "미포", "청사포", "달맞이길"],
    "센텀": ["센텀시티", "벡스코", "영화의전당"],
    "송정": ["송정해수욕장"],
    "서면": ["부전동", "부산시민공원"],
    "남포동": ["자갈치", "자갈치시장", "국제시장", "깡통시장", "BIFF광장", "용두산공원"],
    "부산역": ["초량", "초량동"],
    "송도": ["송도해수욕장", "송도케이블카"],
    "영도": ["태종대", "흰여울", "흰여울문화마을", "봉래동"],
    "동래": ["온천장", "사직", "사직동", "동래역"],
    "부산대학교": ["부산대", "부대", "장전동"],
    "다대포": ["다대포해수욕장", "몰운대"],
    "감천문화마을": ["감천동"],
    "하단": ["하단동", "동아대학교 승학캠퍼스", "동아대"],
    "덕천": ["덕천동", "덕천역"],
    "화명": ["화명동", "화명생태공원"],
    "경성대·부경대": ["경성대", "부경대", "대연동"],
    "용호동": ["오륙도", "이기대"],
    "연산동": ["연산", "연산역"],
    "사상": ["사상역", "괘법동"],
    "명지": ["명지동", "명지국제신도시"],
    "기장": ["기장시장", "대변항", "오시리아"],
    "일광": ["일광해수욕장", "일광신도시"],
    "금정산": ["금정산성", "범어사"],
    "온천천": ["온천천시민공원"],
    "정관": ["정관읍", "정관신도시"],
    "좌동": ["좌동", "장산역"],
    "재송": ["재송동"],
    "반여": ["반여동"],
    "반송": ["반송동"],
    "수영": ["수영동", "수영역", "수영사적공원"],
    "망미": ["망미동", "망미역", "비콘그라운드"],
    "남천": ["남천동", "남천역"],
    "문현": ["문현동", "문현금융단지", "BIFC"],
    "전포": ["전포동", "전포카페거리"],
    "범일": ["범일동", "범일역"],
    "수정": ["수정동", "수정시장"],
    "대신": ["대신동", "동대신동", "서대신동"],
    "토성": ["토성동", "토성역"],
    "괴정": ["괴정동", "괴정역"],
    "장림": ["장림동", "장림포구"],
    "신평": ["신평동", "신평역"],
    "엄궁": ["엄궁동", "엄궁농산물시장"],
    "주례": ["주례동", "주례역"],
    "개금": ["개금동", "개금역"],
    "구포": ["구포동", "구포역", "구포시장"],
    "만덕": ["만덕동", "만덕역"],
    "명륜": ["명륜동", "명륜역"],
    "안락": ["안락동", "충렬사"],
    "부곡": ["부곡동", "부곡시장"],
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Memory Recall API"
    app_version: str = "1.0.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    database_url: str = "sqlite:///./data/memory_recall.db"
    auto_create_tables: bool = True

    storage_backend: Literal["local", "supabase"] = "local"
    local_storage_dir: str = "./data/uploads"
    max_upload_mb: int = 10
    allowed_image_types: str = "image/jpeg,image/png,image/webp"

    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "memory-images"

    ai_mode: Literal["mock", "auto", "upstage"] = "mock"
    ai_fallback_to_mock: bool = True
    upstage_api_key: str | None = None
    upstage_base_url: str = "https://api.upstage.ai/v1"
    upstage_solar_model: str = "solar-pro3"
    upstage_document_parse_url: str = "https://api.upstage.ai/v1/document-digitization"
    upstage_document_parse_model: str = "document-parse"
    upstage_information_extract_url: str = "https://api.upstage.ai/v1/information-extraction"
    upstage_information_extract_model: str = "information-extract"
    upstage_text_render_font_path: str | None = None
    upstage_timeout_seconds: float = 60.0

    card_image_mode: Literal["mock", "auto", "gemini"] = "mock"
    card_image_generation_enabled: bool = True
    gemini_api_key: str | None = None
    nano_banana_model: str = "gemini-3.1-flash-image"
    nano_banana_timeout_seconds: float = 120.0

    demo_mode: bool = False
    demo_day_seconds: int = 2
    first_recall_days: int = 7
    second_recall_days: int = 30
    allow_early_recall: bool = False

    auth_mode: Literal["demo", "header", "supabase"] = "header"
    demo_user_id: str = "demo-user"
    supabase_jwt_secret: str | None = None
    admin_key: str | None = None
    admin_username: str = "admin"
    admin_password: str | None = None
    admin_token_secret: str | None = None
    admin_token_hours: int = 8

    town_min_contributors: int = 3
    share_preview_secret: str = "development-only-change-me"
    place_tags: list[str] = Field(default_factory=lambda: DEFAULT_PLACE_TAGS.copy())

    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    @field_validator("place_tags", "cors_origins", mode="before")
    @classmethod
    def parse_csv_or_list(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                import json

                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @field_validator("demo_day_seconds", "first_recall_days", "second_recall_days")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("값은 0 이상이어야 합니다.")
        return value

    @property
    def allowed_image_type_set(self) -> set[str]:
        return {item.strip() for item in self.allowed_image_types.split(",") if item.strip()}

    @property
    def local_storage_path(self) -> Path:
        return Path(self.local_storage_dir).resolve()

    def validate_runtime_configuration(self) -> None:
        if self.storage_backend == "supabase":
            missing = [
                name
                for name, value in {
                    "SUPABASE_URL": self.supabase_url,
                    "SUPABASE_SERVICE_ROLE_KEY": self.supabase_service_role_key,
                }.items()
                if not value
            ]
            if missing:
                raise RuntimeError(f"Supabase Storage 설정 누락: {', '.join(missing)}")

        if self.ai_mode == "upstage" and not self.upstage_api_key:
            raise RuntimeError("AI_MODE=upstage일 때 UPSTAGE_API_KEY가 필요합니다.")

        if self.card_image_mode == "gemini" and not self.gemini_api_key:
            raise RuntimeError("CARD_IMAGE_MODE=gemini일 때 GEMINI_API_KEY가 필요합니다.")

        if self.auth_mode == "supabase" and not self.supabase_jwt_secret:
            raise RuntimeError("AUTH_MODE=supabase일 때 SUPABASE_JWT_SECRET이 필요합니다.")

        if self.admin_password and not self.admin_token_secret:
            raise RuntimeError("ADMIN_PASSWORD를 설정했다면 ADMIN_TOKEN_SECRET도 필요합니다.")
