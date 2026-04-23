from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.base import Base
from app.db import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_url() -> str:
    # Prefer DATABASE_URL on hosted environments (Render, etc.).
    # Common misconfig: DATABASE_URL is set correctly, but DATABASE_URL_SYNC is left at a
    # localhost default, which breaks migrations during deploy.
    url = os.getenv("DATABASE_URL") or ""
    url_sync = os.getenv("DATABASE_URL_SYNC") or ""
    if url_sync and not url:
        url = url_sync
    elif url_sync and url:
        if "localhost" in url_sync or "127.0.0.1" in url_sync:
            # Ignore localhost sync URL if a non-local async URL exists.
            pass
        else:
            url = url_sync
    if not url:
        raise RuntimeError("DATABASE_URL_SYNC (or DATABASE_URL) must be set for Alembic.")
    # Alembic uses a sync SQLAlchemy engine. Normalize to psycopg (not psycopg2)
    # to avoid build/runtime dependency on psycopg2.
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    elif url.startswith("postgresql+psycopg2://"):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    return url


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
