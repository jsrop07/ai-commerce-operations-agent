"""V2 commerce_ops database session helpers."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_v2_engine(database_url: str) -> Engine:
    """commerce_ops V2 전용 SQLAlchemy engine을 생성한다."""

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


def build_v2_session_factory(
    engine: Engine,
) -> Callable[[], Session]:
    """commerce_ops V2 전용 Session factory를 생성한다."""

    return sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )