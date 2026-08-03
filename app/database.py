from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings):
    kwargs = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    elif "pooler.supabase.com" in settings.database_url:
        # 여러 팀원이 같은 Supabase Session Pooler(pool_size 15)를 사용할 때
        # 각 FastAPI 프로세스의 기본 QueuePool이 유휴 연결을 5개씩 점유하지 않도록 한다.
        # 요청이 끝나면 연결을 즉시 Supavisor에 반환한다.
        kwargs["poolclass"] = NullPool
        if ":6543/" in settings.database_url:
            # Supavisor Transaction Pooler는 prepared statements를 지원하지 않는다.
            kwargs["connect_args"] = {"prepare_threshold": None}
    return create_engine(settings.database_url, **kwargs)


def build_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
