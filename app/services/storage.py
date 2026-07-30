from __future__ import annotations

import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from app.config import Settings
from app.constants import ALLOWED_IMAGE_EXTENSIONS
from app.errors import ServiceError


@dataclass
class StoredFile:
    path: str
    filename: str
    content_type: str
    size: int


class StorageBackend(Protocol):
    def save(self, *, owner_id: str, filename: str, content_type: str, data: bytes) -> StoredFile: ...
    def read(self, path: str) -> tuple[bytes, str]: ...
    def delete(self, path: str) -> None: ...


class LocalStorage:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.local_storage_path
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, *, owner_id: str, filename: str, content_type: str, data: bytes) -> StoredFile:
        suffix = Path(filename).suffix.lower() or ALLOWED_IMAGE_EXTENSIONS.get(content_type, ".bin")
        safe_owner = "".join(ch for ch in owner_id if ch.isalnum() or ch in "-_" ) or "user"
        relative = Path(safe_owner) / f"{uuid.uuid4()}{suffix}"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return StoredFile(path=relative.as_posix(), filename=filename, content_type=content_type, size=len(data))

    def read(self, path: str) -> tuple[bytes, str]:
        target = (self.root / path).resolve()
        if self.root not in target.parents and target != self.root:
            raise ServiceError("잘못된 저장 경로입니다.", status_code=400)
        if not target.exists():
            raise ServiceError("이미지 파일을 찾을 수 없습니다.", status_code=404)
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return target.read_bytes(), content_type

    def delete(self, path: str) -> None:
        target = (self.root / path).resolve()
        if target.exists() and self.root in target.parents:
            target.unlink()


class SupabaseStorage:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.validate_runtime_configuration()
        self.base = settings.supabase_url.rstrip("/")
        self.key = settings.supabase_service_role_key
        self.bucket = settings.supabase_storage_bucket

    @property
    def headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }

    def save(self, *, owner_id: str, filename: str, content_type: str, data: bytes) -> StoredFile:
        suffix = Path(filename).suffix.lower() or ALLOWED_IMAGE_EXTENSIONS.get(content_type, ".bin")
        safe_owner = "".join(ch for ch in owner_id if ch.isalnum() or ch in "-_" ) or "user"
        path = f"{safe_owner}/{uuid.uuid4()}{suffix}"
        url = f"{self.base}/storage/v1/object/{self.bucket}/{path}"
        headers = {**self.headers, "Content-Type": content_type, "x-upsert": "false"}
        try:
            response = httpx.post(url, headers=headers, content=data, timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ServiceError("Supabase Storage 업로드에 실패했습니다.", detail={"error": str(exc)}) from exc
        return StoredFile(path=path, filename=filename, content_type=content_type, size=len(data))

    def read(self, path: str) -> tuple[bytes, str]:
        url = f"{self.base}/storage/v1/object/authenticated/{self.bucket}/{path}"
        try:
            response = httpx.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            status = 404 if getattr(exc, "response", None) is not None and exc.response.status_code == 404 else 502
            raise ServiceError("Supabase Storage에서 이미지를 읽지 못했습니다.", status_code=status) from exc
        return response.content, response.headers.get("content-type", "application/octet-stream")

    def delete(self, path: str) -> None:
        url = f"{self.base}/storage/v1/object/{self.bucket}"
        try:
            response = httpx.request("DELETE", url, headers={**self.headers, "Content-Type": "application/json"}, json={"prefixes": [path]}, timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ServiceError("Supabase Storage 이미지 삭제에 실패했습니다.", detail={"error": str(exc)}) from exc


def build_storage(settings: Settings) -> StorageBackend:
    if settings.storage_backend == "supabase":
        return SupabaseStorage(settings)
    return LocalStorage(settings)
