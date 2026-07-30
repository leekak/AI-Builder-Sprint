from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, archive, cards, health, memories, recalls
from app.config import Settings
from app.database import Base, build_engine, build_session_factory
from app.errors import ServiceError
from app.services.ai import AIService
from app.services.card_image import CardImageService
from app.services.storage import build_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.validate_runtime_configuration()

    engine = build_engine(settings)
    SessionLocal = build_session_factory(engine)
    storage = build_storage(settings)
    ai = AIService(settings)
    card_image_service = CardImageService(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_create_tables:
            Base.metadata.create_all(bind=engine)
        yield
        engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "사진을 보기 전에 기억을 떠올리고, 원본 공개 후 새롭게 떠오른 내용을 더해 "
            "하나의 추억 카드로 완성하는 API입니다. 기억의 정확도를 평가하지 않습니다."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.SessionLocal = SessionLocal
    app.state.storage = storage
    app.state.ai = ai
    app.state.card_image_service = card_image_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False if "*" in settings.cors_origins else True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, exc: ServiceError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"message": exc.message, **exc.detail}},
        )

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/demo/")

    app.include_router(health.router)
    app.include_router(memories.router)
    app.include_router(recalls.router)
    app.include_router(cards.router)
    app.include_router(archive.router)
    app.include_router(admin.router)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/demo", StaticFiles(directory=str(static_dir), html=True), name="demo")
    return app


app = create_app()
