import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the project root to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import the Base and ALL models for autogenerate support
from app.core.database import Base  # noqa: E402
import app.models  # noqa: E402, F401 - Import all models so metadata is populated

target_metadata = Base.metadata

# This is the Alembic Config object
config = context.config

# PER AGENTS-BACKEND.md: Do NOT call fileConfig() to avoid resetting FastAPI loggers

# Set sqlalchemy.url from environment variable
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
