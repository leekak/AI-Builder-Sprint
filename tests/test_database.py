from __future__ import annotations

from unittest.mock import patch

from sqlalchemy.pool import NullPool

from app.config import Settings
from app.database import build_engine


def test_supabase_pooler_does_not_keep_idle_connections():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:pass@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres",
    )
    engine = build_engine(settings)
    assert isinstance(engine.pool, NullPool)
    engine.dispose()


def test_transaction_pooler_disables_psycopg_prepared_statements():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:pass@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres",
    )
    with patch("app.database.create_engine") as create_engine:
        build_engine(settings)
    kwargs = create_engine.call_args.kwargs
    assert kwargs["poolclass"] is NullPool
    assert kwargs["connect_args"]["prepare_threshold"] is None
