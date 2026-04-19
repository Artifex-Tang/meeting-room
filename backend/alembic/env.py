import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

# Make sure `app` package is importable when running alembic from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import Base + all models so their tables are registered in metadata
from app.models import Base  # noqa: E402

# Use pydantic-settings to load DATABASE_URL (reads .env automatically)
from app.config import settings  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    return settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_get_url())
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
