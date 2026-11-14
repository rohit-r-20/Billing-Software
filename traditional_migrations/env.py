import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import create_engine, pool
from alembic import context

# Prepend application root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from db.traditional_database import (
    traditional_db_manager,
    validate_traditional_database_target,
    TraditionalConfigurationError,
)
from db.traditional_models import TraditionalBase

# Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = TraditionalBase.metadata


def get_active_traditional_url() -> str:
    """
    Retrieve and strictly validate the active Traditional Billing database URL.
    Prohibits fallback to Fast Billing database.
    """
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url and ini_url.strip() and not ini_url.startswith("driver://"):
        target_url = ini_url.strip()
    else:
        target_url = traditional_db_manager.database_url

    # Strict validation guard
    validate_traditional_database_target(target_url)

    if target_url.startswith("postgres://"):
        target_url = "postgresql+psycopg://" + target_url[len("postgres://"):]
    elif target_url.startswith("postgresql://"):
        target_url = "postgresql+psycopg://" + target_url[len("postgresql://"):]

    return target_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_active_traditional_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="traditional_alembic_version",
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_active_traditional_url()
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            version_table="traditional_alembic_version",
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
