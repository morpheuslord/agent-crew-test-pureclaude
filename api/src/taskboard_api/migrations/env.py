"""Alembic environment. Migrations run under a PostgreSQL advisory lock."""

import os

from alembic import context
from sqlalchemy import create_engine, pool, text

from taskboard_api.models import Base

# Any constant works; it only has to be the same for every instance running migrations.
_MIGRATION_LOCK_KEY = 7_311_204_118

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or os.environ["DATABASE_URL"]


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            # Serialises concurrent starts of several API instances; released at commit.
            connection.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": _MIGRATION_LOCK_KEY}
            )
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
