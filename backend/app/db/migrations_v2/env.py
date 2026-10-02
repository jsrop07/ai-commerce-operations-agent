"""Alembic environment for commerce_ops V2."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

import backend.app.models_v2  # noqa: F401
from backend.app.db.base_v2 import BaseV2


config = context.config

postgres_v2_url = os.getenv("POSTGRES_V2_URL")
if postgres_v2_url:
    config.set_main_option(
        "sqlalchemy.url",
        postgres_v2_url.replace("%", "%%"),
    )

target_metadata = BaseV2.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema="public",
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            version_table="alembic_version",
            version_table_schema="public",
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()

def include_object(
    object,
    name,
    type_,
    reflected,
    compare_to,
):
    if type_ == "table" and name == "alembic_version":
        return False
    return True

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()