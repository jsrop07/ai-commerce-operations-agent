"""Backend DB engine 생성."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine


def build_engine(
    database_url: str,
) -> Engine:
    kwargs: dict[str, object] = {
        "pool_pre_ping": True,
    }

    if database_url.startswith(
        "sqlite"
    ):
        kwargs["connect_args"] = {
            "check_same_thread": False,
        }

    return create_engine(
        database_url,
        **kwargs,
    )