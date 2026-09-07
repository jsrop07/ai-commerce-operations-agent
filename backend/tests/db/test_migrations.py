import os
import subprocess
import sys

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

import backend.app.models  # noqa: F401
from backend.app.db.base import Base


def test_postgresql_offline_upgrade_and_downgrade_sql_compile() -> None:
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "CREATE TABLE" in upgrade.stdout
    assert "inventory_ledger" in upgrade.stdout
    assert "sync_states" in upgrade.stdout
    assert "fk_skus_product_same_tenant" in upgrade.stdout
    assert "fk_sale_events_sku_same_tenant" in upgrade.stdout
    assert "fk_task_dependencies_successor_same_tenant" in upgrade.stdout
    assert "ck_reservation_aging_nonnegative" in upgrade.stdout
    assert "ck_task_status_allowed" in upgrade.stdout
    downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "head:base", "--sql"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "DROP TABLE" in downgrade.stdout


@pytest.mark.postgres
def test_live_postgresql_upgrade_schema_and_rollback() -> None:
    url = os.getenv("POSTGRES_TEST_URL")
    if not url:
        pytest.skip("BLOCKED_BY_LOCAL_DB: POSTGRES_TEST_URL is not configured")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(url)
    inspector = inspect(engine)
    assert set(Base.metadata.tables) <= set(inspector.get_table_names())
    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        assert compare_metadata(migration_context, Base.metadata) == []
        trigger_count = connection.scalar(
            text(
                """
                SELECT count(*)
                FROM pg_trigger
                WHERE tgname = 'inventory_ledger_append_only' AND NOT tgisinternal
                """
            )
        )
        assert trigger_count == 1

    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT to_regprocedure('prevent_inventory_ledger_mutation()')"))
            is None
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "f38aa7ef5019"
    engine.dispose()
