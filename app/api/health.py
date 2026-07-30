from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import get_settings
from app.schemas import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "ai_mode": settings.ai_mode,
        "storage_backend": settings.storage_backend,
        "demo_mode": settings.demo_mode,
        "time": datetime.now(timezone.utc),
    }
