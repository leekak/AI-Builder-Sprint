from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings
from app.dependencies import get_settings, require_admin_account
from app.schemas import AdminLoginRequest, AdminSessionResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=AdminSessionResponse)
def admin_login(payload: AdminLoginRequest, settings: Settings = Depends(get_settings)):
    if not settings.admin_password or not settings.admin_token_secret:
        raise HTTPException(status_code=503, detail="관리자 계정이 아직 설정되지 않았습니다.")
    valid_username = hmac.compare_digest(payload.username, settings.admin_username)
    valid_password = hmac.compare_digest(payload.password, settings.admin_password)
    if not valid_username or not valid_password:
        raise HTTPException(status_code=401, detail="관리자 아이디 또는 비밀번호가 올바르지 않습니다.")

    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.admin_token_hours)
    token = jwt.encode(
        {"sub": settings.admin_username, "role": "admin", "exp": expires_at},
        settings.admin_token_secret,
        algorithm="HS256",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": settings.admin_username,
        "expires_at": expires_at,
    }


@router.get("/me")
def admin_me(username: str = Depends(require_admin_account)):
    return {"username": username, "role": "admin"}
