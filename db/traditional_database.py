"""
Traditional Billing Database Management Layer.
Dedicated connection manager, engine pools, and transactional scopes for Traditional Billing.
Completely isolated from Fast Billing (data/anti_matrix_billing.db).
"""

import os
import re
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Generator, Any

from sqlalchemy import create_engine, Engine, event, text
from sqlalchemy.orm import sessionmaker, Session

from core.configuration import config
from core.logging_config import logger


class TraditionalConfigurationError(Exception):
    """Raised when Traditional Billing is misconfigured or attempts to use Fast Billing storage."""
    pass


def validate_traditional_database_target(url_or_path: str) -> None:
    """
    Strict validation guard:
    Ensures Traditional Billing never falls back to or operates on the Fast Billing database.
    """
    if not url_or_path:
        raise TraditionalConfigurationError("Traditional Billing database URL or path cannot be empty.")

    normalized = str(url_or_path).strip().lower()

    # Reject any reference to Fast Billing SQLite database
    fast_db_name = "anti_matrix_billing.db"
    if fast_db_name in normalized:
        raise TraditionalConfigurationError(
            f"FATAL: Traditional Billing cannot connect to or operate on Fast Billing database ({url_or_path})."
        )

    # Reject if it exactly matches Fast Billing configured path
    fast_configured_path = str(config.DATABASE_PATH).strip().lower()
    if normalized == fast_configured_path or normalized.endswith(fast_configured_path):
        raise TraditionalConfigurationError(
            "FATAL: Traditional Billing cannot use Fast Billing configured database path."
        )


class TraditionalDatabaseManager:
    """
    Database connection manager for Traditional Billing.
    Maintains separate engines for read and write operations (SQLite WAL + query_only),
    or connection-pooled engines for PostgreSQL.
    """

    def __init__(self, database_url: Optional[str] = None):
        self._custom_url = database_url
        self._url: Optional[str] = None
        self._write_engine: Optional[Engine] = None
        self._read_engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._read_session_factory: Optional[sessionmaker] = None
        self._init_manager()

    def _resolve_database_url(self) -> str:
        """Resolves target database URL, enforcing strict isolation validation."""
        if self._custom_url:
            target = self._custom_url
        else:
            env_url = os.environ.get("TRADITIONAL_DATABASE_URL")
            if env_url and env_url.strip():
                target = env_url.strip()
            else:
                default_sqlite_path = Path("data/traditional_billing.db").resolve()
                target = f"sqlite:///{default_sqlite_path}"

        validate_traditional_database_target(target)
        return target

    @property
    def database_url(self) -> str:
        if self._url is None:
            self._url = self._resolve_database_url()
        return self._url

    @property
    def is_postgres(self) -> bool:
        u = self.database_url.lower()
        return u.startswith("postgres://") or u.startswith("postgresql://") or u.startswith("postgresql+")

    @property
    def is_sqlite(self) -> bool:
        return not self.is_postgres

    def _normalize_sqlalchemy_url(self, url: str) -> str:
        """Ensures driver prefix is postgresql+psycopg for SQLAlchemy 2.x."""
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    def _init_manager(self) -> None:
        """Initializes isolated engines for Traditional Billing."""
        resolved_url = self.database_url
        norm_url = self._normalize_sqlalchemy_url(resolved_url)

        if self.is_postgres:
            # PostgreSQL: unified engine with connection pool
            pool_opts = config.get_pool_config()
            self._write_engine = create_engine(
                norm_url,
                pool_pre_ping=pool_opts.get("pool_pre_ping", True),
                pool_size=pool_opts.get("pool_size", 5),
                max_overflow=pool_opts.get("max_overflow", 10),
                pool_timeout=pool_opts.get("pool_timeout", 30),
                pool_recycle=pool_opts.get("pool_recycle", 1800),
            )
            self._read_engine = self._write_engine
        else:
            # SQLite: ensure parent directory exists
            clean_path = resolved_url.replace("sqlite:///", "").replace("sqlite://", "")
            if clean_path and clean_path != ":memory:":
                Path(clean_path).parent.mkdir(parents=True, exist_ok=True)

            # SQLite Write Engine (WAL + BEGIN IMMEDIATE)
            self._write_engine = create_engine(norm_url, echo=False)

            @event.listens_for(self._write_engine, "connect")
            def _set_sqlite_write_pragmas(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode = WAL;")
                cursor.execute("PRAGMA foreign_keys = ON;")
                cursor.execute("PRAGMA busy_timeout = 30000;")
                cursor.execute("PRAGMA synchronous = NORMAL;")
                cursor.close()

            @event.listens_for(self._write_engine, "begin")
            def _sqlite_begin_immediate(conn):
                # Acquire write lock immediately to eliminate SQLITE_BUSY deadlocks
                conn.execute(text("BEGIN IMMEDIATE"))

            # SQLite Read Engine (query_only = ON)
            self._read_engine = create_engine(norm_url, echo=False)

            @event.listens_for(self._read_engine, "connect")
            def _set_sqlite_read_pragmas(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA query_only = ON;")
                cursor.execute("PRAGMA foreign_keys = ON;")
                cursor.execute("PRAGMA busy_timeout = 5000;")
                cursor.close()

        self._session_factory = sessionmaker(bind=self._write_engine, expire_on_commit=False)
        self._read_session_factory = sessionmaker(bind=self._read_engine, expire_on_commit=False)

    @property
    def write_engine(self) -> Engine:
        if self._write_engine is None:
            self._init_manager()
        return self._write_engine

    @property
    def read_engine(self) -> Engine:
        if self._read_engine is None:
            self._init_manager()
        return self._read_engine

    @property
    def engine(self) -> Engine:
        """Default engine (write engine)."""
        return self.write_engine

    def get_session(self) -> Session:
        """Returns a new transactional Session bound to the write engine."""
        if self._session_factory is None:
            self._init_manager()
        return self._session_factory()

    def get_read_session(self) -> Session:
        """Returns a read-only Session bound to the read engine."""
        if self._read_session_factory is None:
            self._init_manager()
        return self._read_session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Transactional context manager for write sessions.
        Commits on normal exit, rolls back on exception, always closes.
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def read_session_scope(self) -> Generator[Session, None, None]:
        """
        Read-only session context manager.
        Closes cleanly without committing.
        """
        session = self.get_read_session()
        try:
            yield session
        finally:
            session.close()

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Provides a DB connection context (read engine)."""
        conn = self.read_engine.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def get_write_connection(self) -> Generator[Any, None, None]:
        """Provides a DB connection context (write engine)."""
        conn = self.write_engine.connect()
        try:
            yield conn
        finally:
            conn.close()

    def run_traditional_migrations(self) -> bool:
        """
        Executes Alembic migrations for Traditional Billing up to 'head'.
        Strict security rules:
        1. Validates target database URL. Rejects any reference to Fast Billing database.
        2. If target is PostgreSQL or external/production database, refuses automatic execution
           and logs that explicit migration authorization is required.
        3. If target is local SQLite, applies migrations using traditional_alembic.ini and
           traditional_migrations/ in order through 'head'.
        4. Does NOT use Base.metadata.create_all() as a substitute.
        5. Sanitizes error messages to prevent credential leakage.
        """
        validate_traditional_database_target(self.database_url)

        if self.is_postgres:
            logger.warning(
                "Traditional Billing database target is PostgreSQL. "
                "Automatic startup migrations are disabled for external/production databases. "
                "Explicit migration authorization is required."
            )
            return False

        from alembic.config import Config as AlembicConfig
        from alembic import command

        ini_path = Path("traditional_alembic.ini").resolve()
        if not ini_path.exists():
            raise FileNotFoundError(f"Missing traditional_alembic.ini at {ini_path}")

        escaped_url = self.database_url.replace("%", "%%")
        alembic_cfg = AlembicConfig(str(ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", escaped_url)

        try:
            logger.info("Executing Traditional Billing migrations to head...")
            command.upgrade(alembic_cfg, "head")
            logger.info("Traditional Billing migrations completed successfully.")
            return True
        except Exception as e:
            err_msg = str(e)
            if "@" in err_msg:
                err_msg = re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", err_msg)
            logger.error(f"Traditional Billing migration failed: {err_msg}")
            raise RuntimeError(f"Traditional Billing migration error: {err_msg}") from None

    def ensure_initialized(self) -> None:
        """
        For SQLite, ensures the database schema is migrated before operations.
        Safe to call multiple times (Alembic checks current version).
        """
        if self.is_sqlite:
            self.run_traditional_migrations()

    def close(self) -> None:
        """Closes all underlying engines."""
        if self._write_engine:
            self._write_engine.dispose()
        if self._read_engine and self._read_engine != self._write_engine:
            self._read_engine.dispose()


# Global singleton instance for Traditional Billing
traditional_db_manager = TraditionalDatabaseManager()
