from __future__ import annotations

from collections.abc import Generator

import jwt
from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.services.ai import AIService
from app.services.storage import StorageBackend
from app.services.card_image import CardImageService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_storage(request: Request) -> StorageBackend:
    return request.app.state.storage


def get_ai(request: Request) -> AIService:
    return request.app.state.ai


def get_card_image_service(request: Request) -> CardImageService:
    return request.app.state.card_image_service


def get_current_user_id(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    settings: Settings = request.app.state.settings

    if settings.auth_mode == "demo":
        return (x_user_id or settings.demo_user_id).strip()

    if settings.auth_mode == "header":
        if not x_user_id or not x_user_id.strip():
            raise HTTPException(status_code=401, detail="X-User-Id 헤더가 필요합니다.")
        return x_user_id.strip()

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer 인증 토큰이 필요합니다.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 토큰입니다.") from exc
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=401, detail="토큰에 사용자 식별자(sub)가 없습니다.")
    return str(subject)


def require_admin(
    request: Request,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    settings: Settings = request.app.state.settings
    if settings.admin_key and x_admin_key == settings.admin_key:
        return
    if settings.admin_token_secret and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, settings.admin_token_secret, algorithms=["HS256"])
            if payload.get("role") == "admin":
                return
        except jwt.PyJWTError:
            pass
    if not settings.admin_key and not settings.admin_password:
        return
    raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")


def require_admin_account(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    settings: Settings = request.app.state.settings
    if not settings.admin_password or not settings.admin_token_secret:
        raise HTTPException(status_code=503, detail="관리자 계정이 아직 설정되지 않았습니다.")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="관리자 로그인이 필요합니다.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.admin_token_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="관리자 세션이 만료되었거나 유효하지 않습니다.") from exc
    if payload.get("role") != "admin" or payload.get("sub") != settings.admin_username:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return settings.admin_username
