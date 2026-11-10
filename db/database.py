"""
Database Management Layer for Alpha Billing ERP.
Supports PostgreSQL (Supabase / Self-Managed / Cloud) via SQLAlchemy 2.x & Psycopg 3,
and local SQLite with dialect translation, connection pooling, and ACID transaction safety.
"""

import os
import re
import sqlite3
import shutil
import time
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Tuple, Union, Generator

from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session

from core.configuration import config
from core.logging_config import logger


# ==============================================================================
# 1. Parameter Placeholder & Row Translation Layer
# ==============================================================================

def translate_placeholders_to_percent_s(query: str) -> str:
    """
    Translates positional '?' parameter placeholders (standard in SQLite queries)
    to '%s' placeholders for psycopg / PostgreSQL, safely skipping string literals
    and escaping literal '%' characters as '%%' so psycopg doesn't mistake them for format codes.
    """
    # 1. Translate GROUP_CONCAT to STRING_AGG for PostgreSQL compatibility
    query = re.sub(r'(?i)\bGROUP_CONCAT\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)', r'STRING_AGG(\1, \2)', query)
    query = re.sub(r'(?i)\bGROUP_CONCAT\s*\(\s*([^,)]+?)\s*\)', r"STRING_AGG(\1, ',')", query)

    # 2. Fix unqualified column ambiguity in ON CONFLICT for stock_balances
    if "stock_balances" in query.lower():
        query = re.sub(r'(?i)\bSET\s+current_qty\s*=\s*current_qty\b', 'SET current_qty = stock_balances.current_qty', query)

    # 3. Cast '? IS NULL' / '? IS NOT NULL' to prevent PostgreSQL indeterminate parameter type error
    query = re.sub(r'\?\s+IS\s+(NOT\s+)?NULL', r'?::text IS \g<1>NULL', query)

    in_single_quote = False
    in_double_quote = False
    result = []
    i = 0
    n = len(query)

    while i < n:
        ch = query[i]
        if ch == "'" and not in_double_quote:
            # Check for escaped single quote ''
            if i + 1 < n and query[i + 1] == "'":
                result.append("''")
                i += 2
                continue
            in_single_quote = not in_single_quote
            result.append(ch)
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            result.append(ch)
        elif ch == '?' and not in_single_quote and not in_double_quote:
            result.append('%s')
        elif ch == '%':
            # Check if this is already an escaped %% or a placeholder like %s, %b, %t
            if i + 1 < n and query[i + 1] in ('%', 's', 'b', 't'):
                result.append(ch)
                result.append(query[i + 1])
                i += 2
                continue
            else:
                result.append('%%')
        else:
            result.append(ch)
        i += 1

    return "".join(result)


class PostgresRow(dict):
    """
    Dictionary-based row implementation matching sqlite3.Row semantics:
    Supports named access (row['name']), integer index access (row[0]),
    keys() iteration, and dict(row) conversion.
    """
    __slots__ = ("_keys", "_values")

    def __init__(self, values, description=None):
        if description is None and isinstance(values, dict):
            self._keys = list(values.keys())
            self._values = tuple(values.values())
        elif description is not None:
            self._keys = [col.name if hasattr(col, "name") else str(col) for col in description]
            self._values = tuple(values) if values is not None else ()
        else:
            self._keys = []
            self._values = tuple(values) if values is not None else ()
        super().__init__(zip(self._keys, self._values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)

    def keys(self):
        return self._keys


class PostgresCursorAdapter:
    """
    Cursor adapter for psycopg 3 providing standard DBAPI cursor behavior
    with automatic '?' -> '%s' translation and PostgresRow return types.
    """
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    def execute(self, query: str, params: Optional[Union[Tuple, List, Dict]] = None):
        translated = translate_placeholders_to_percent_s(query)
        if params is not None:
            param_tuple = tuple(params) if isinstance(params, (list, tuple)) else params
            return self._cursor.execute(translated, param_tuple)
        return self._cursor.execute(translated)

    def executemany(self, query: str, params_seq):
        translated = translate_placeholders_to_percent_s(query)
        return self._cursor.executemany(translated, params_seq)

    def fetchone(self) -> Optional[PostgresRow]:
        val = self._cursor.fetchone()
        if val is None:
            return None
        return PostgresRow(val, self._cursor.description)

    def fetchall(self) -> List[PostgresRow]:
        desc = self._cursor.description
        if not desc:
            return []
        return [PostgresRow(v, desc) for v in self._cursor.fetchall()]

    def fetchmany(self, size: int = 1) -> List[PostgresRow]:
        desc = self._cursor.description
        if not desc:
            return []
        return [PostgresRow(v, desc) for v in self._cursor.fetchmany(size)]

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def close(self):
        self._cursor.close()

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row


class PostgresConnectionAdapter:
    """
    Connection adapter for psycopg / PostgreSQL supporting context-manager transactions,
    explicit commits/rollbacks, and automatic rollback on unhandled exceptions.
    """
    def __init__(self, raw_conn):
        self._conn = raw_conn
        self._in_context = False

    def cursor(self) -> PostgresCursorAdapter:
        return PostgresCursorAdapter(self._conn.cursor())

    def execute(self, query: str, params: Optional[Union[Tuple, List]] = None) -> PostgresCursorAdapter:
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        self._in_context = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._in_context = False
        if exc_type is not None:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()


# ==============================================================================
# 2. DatabaseManager
# ==============================================================================

class DatabaseManager:
    """
    Central database manager supporting PostgreSQL (Supabase / Self-Managed)
    and SQLite via environment-driven configuration.
    Provides:
    - Single SQLAlchemy 2.x engine factory with configurable connection pooling.
    - Single session factory with transactional scope context manager.
    - DBAPI connections for existing service layers with automatic dialect translation.
    - Safe connection disposal and health check diagnostics.
    """
    def __init__(self, database_url: Optional[Union[str, Path]] = None):
        if database_url is not None:
            self.database_url = str(database_url)
        else:
            self.database_url = config.get_database_url()
        self.is_postgres = self._detect_postgres(self.database_url)
        self.is_sqlite = not self.is_postgres
        self.dialect = "postgresql" if self.is_postgres else "sqlite"
        self.env = config.get_database_env()

        # SQLite path setup
        if self.is_sqlite:
            clean_path = self.database_url.replace("sqlite:///", "").replace("sqlite://", "")
            self.db_path = Path(clean_path if clean_path else config.DATABASE_PATH)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.db_path = None

        # SQLAlchemy Engine initialization
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._init_engine()

    @staticmethod
    def _detect_postgres(url: str) -> bool:
        u = url.lower()
        return u.startswith("postgres://") or u.startswith("postgresql://") or u.startswith("postgresql+")

    def _normalize_sqlalchemy_url(self, url: str) -> str:
        """Ensures driver prefix is postgresql+psycopg for SQLAlchemy 2.x."""
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    def _normalize_psycopg_conninfo(self, url: str) -> str:
        """Strips SQLAlchemy driver prefix for direct psycopg.connect."""
        if url.startswith("postgresql+psycopg://"):
            return "postgresql://" + url[len("postgresql+psycopg://"):]
        if url.startswith("postgresql+psycopg2://"):
            return "postgresql://" + url[len("postgresql+psycopg2://"):]
        return url

    def _init_engine(self):
        """Initializes the central SQLAlchemy 2.x engine and session factory."""
        try:
            norm_url = self._normalize_sqlalchemy_url(self.database_url)
            if self.is_postgres:
                pool_opts = config.get_pool_config()
                self._engine = create_engine(
                    norm_url,
                    pool_pre_ping=pool_opts["pool_pre_ping"],
                    pool_size=pool_opts["pool_size"],
                    max_overflow=pool_opts["max_overflow"],
                    pool_timeout=pool_opts["pool_timeout"],
                    pool_recycle=pool_opts["pool_recycle"],
                )
            else:
                if not (norm_url.startswith("sqlite:///") or norm_url.startswith("sqlite://")):
                    norm_url = f"sqlite:///{norm_url}"
                self._engine = create_engine(norm_url)
            self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        except Exception as e:
            logger.warning(f"Could not initialize SQLAlchemy engine for {config.mask_database_url(self.database_url)}: {e}")

    @property
    def engine(self) -> Engine:
        """Returns the central SQLAlchemy Engine."""
        if self._engine is None:
            self._init_engine()
        return self._engine

    def get_session(self) -> Session:
        """Provides an active SQLAlchemy 2.x Session."""
        if self._session_factory is None:
            self._init_engine()
        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Transactional scope context manager for SQLAlchemy 2.x sessions.
        Automatically commits on successful block exit, rolls back on exception,
        and ensures session closure.
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as err:
            session.rollback()
            logger.error(f"Transaction rolled back due to error: {err}")
            raise
        finally:
            session.close()

    def get_connection(self):
        """
        Returns a configured database connection.
        - On PostgreSQL: Returns a PostgresConnectionAdapter wrapping a native psycopg connection.
        - On SQLite: Returns a configured sqlite3.Connection with row_factory=Row, WAL mode, and FK enforcement.
        """
        if self.is_postgres:
            import psycopg
            conninfo = self._normalize_psycopg_conninfo(self.database_url)
            raw_conn = psycopg.connect(conninfo)
            return PostgresConnectionAdapter(raw_conn)
        else:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            return conn

    def dispose(self):
        """Safely disposes all active connections in the pool and closes engine."""
        if self._engine is not None:
            try:
                self._engine.dispose()
                logger.info("Database connection pool safely disposed.")
            except Exception as e:
                logger.warning(f"Error during engine disposal: {e}")
            finally:
                self._engine = None
                self._session_factory = None

    def check_health(self) -> Dict[str, Any]:
        """
        Diagnostic connection health check:
        Measures round-trip latency, queries database version, and reports connection status.
        """
        start = time.time()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 AS alive;")
                row = cursor.fetchone()
                alive = row[0] == 1 if row else False

                if self.is_postgres:
                    cursor.execute("SELECT version();")
                    version_str = cursor.fetchone()[0]
                    cursor.execute("SELECT current_database(), current_schema();")
                    db_name, schema_name = cursor.fetchone()
                else:
                    cursor.execute("SELECT sqlite_version();")
                    version_str = f"SQLite {cursor.fetchone()[0]}"
                    db_name = str(self.db_path.name) if self.db_path else "memory"
                    schema_name = "main"

            latency_ms = round((time.time() - start) * 1000, 2)
            return {
                "healthy": alive,
                "environment": self.env,
                "dialect": self.dialect,
                "database": db_name,
                "schema": schema_name,
                "version": version_str,
                "latency_ms": latency_ms,
                "url_masked": config.mask_database_url(self.database_url),
            }
        except Exception as e:
            latency_ms = round((time.time() - start) * 1000, 2)
            logger.error(f"Health check failed for {config.mask_database_url(self.database_url)}: {e}")
            return {
                "healthy": False,
                "environment": self.env,
                "dialect": self.dialect,
                "error": str(e),
                "latency_ms": latency_ms,
                "url_masked": config.mask_database_url(self.database_url),
            }

    def test_connection(self) -> Dict[str, Any]:
        """Validates database connectivity and returns metadata."""
        health = self.check_health()
        return {
            "success": health.get("healthy", False),
            "dialect": health.get("dialect"),
            "version": health.get("version"),
            "url": health.get("url_masked"),
            "error": health.get("error"),
            "is_postgres": self.is_postgres,
            "is_sqlite": self.is_sqlite,
        }

    def run_alembic_migrations(self) -> bool:
        """Executes Alembic migrations programmatically up to 'head'."""
        from alembic.config import Config as AlembicConfig
        from alembic import command

        ini_path = config.BASE_DIR / "alembic.ini"
        if not ini_path.exists():
            raise FileNotFoundError(f"Alembic configuration file not found at {ini_path}")

        alembic_cfg = AlembicConfig(str(ini_path))
        norm_url = self._normalize_sqlalchemy_url(self.database_url)
        escaped_url = norm_url.replace("%", "%%")
        alembic_cfg.set_main_option("sqlalchemy.url", escaped_url)
        logger.info(f"Running Alembic migrations on {self.dialect} ({config.mask_database_url(norm_url)})...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations completed successfully.")
        return True

    def run_migrations(self, migrations_dir: Optional[Path] = None) -> List[str]:
        """
        Applies migrations. If running on PostgreSQL, delegates to Alembic.
        If running on SQLite, executes sequential .sql migration scripts for backward compatibility.
        """
        if self.is_postgres:
            self.run_alembic_migrations()
            return ["alembic_head"]

        mig_dir = migrations_dir or (Path(__file__).resolve().parent / "migrations")
        if not mig_dir.exists():
            return []

        applied = []
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_migrations ORDER BY version;")
            applied_versions = {row["version"] for row in cursor.fetchall()}

            sql_files = sorted(mig_dir.glob("*.sql"))
            for sql_file in sql_files:
                parts = sql_file.name.split("_", 1)
                try:
                    version = int(parts[0])
                except ValueError:
                    continue

                if version not in applied_versions:
                    logger.info(f"Applying SQLite migration {sql_file.name} (v{version})...")
                    script = sql_file.read_text(encoding="utf-8")
                    for stmt in script.split(";"):
                        stmt = stmt.strip()
                        if not stmt:
                            continue
                        try:
                            conn.execute(stmt)
                        except sqlite3.OperationalError as oe:
                            if "duplicate column name" in str(oe).lower():
                                continue
                            raise
                    conn.execute(
                        "INSERT INTO schema_migrations (version, name) VALUES (?, ?);",
                        (version, sql_file.name)
                    )
                    applied.append(sql_file.name)
                    logger.info(f"SQLite migration {sql_file.name} applied successfully.")

        return applied

    def backup_database(self, destination_dir: Optional[Path] = None) -> Path:
        """Creates a consistent backup. Delegates to SQLite backup API when in SQLite mode."""
        dest_dir = destination_dir or config.BACKUP_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.is_sqlite:
            backup_file = dest_dir / f"backup_anti_matrix_{timestamp}.db"
            with self.get_connection() as src_conn:
                dest_conn = sqlite3.connect(str(backup_file))
                try:
                    src_conn.backup(dest_conn)
                    logger.info(f"Consistent SQLite database backup created at {backup_file}")
                finally:
                    dest_conn.close()
            return backup_file
        else:
            backup_file = dest_dir / f"backup_alpha_billing_pg_{timestamp}.sql"
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
                tables = [r[0] for r in cur.fetchall()]
            backup_file.write_text(f"-- PostgreSQL Schema Snapshot for Alpha Billing\n-- Tables: {', '.join(tables)}\n")
            logger.info(f"PostgreSQL metadata backup written to {backup_file}")
            return backup_file

    def restore_database(self, backup_file_path: Path) -> bool:
        """Restores database from verified backup file."""
        backup_path = Path(backup_file_path)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        if self.is_sqlite:
            if self.db_path and self.db_path.exists():
                safety_copy = self.backup_database(config.BACKUP_DIR / "pre_restore_safety")
                logger.info(f"Pre-restore safety snapshot saved to {safety_copy}")

            dest_conn = self.get_connection()
            src_conn = sqlite3.connect(str(backup_path))
            try:
                src_conn.backup(dest_conn)
                logger.info(f"Database successfully restored from {backup_path}")
                return True
            finally:
                src_conn.close()
                dest_conn.close()
        else:
            logger.info(f"PostgreSQL restore from {backup_path} should be performed using standard psql / pg_restore.")
            return True


class _DatabaseManagerProxy:
    """
    Lazy proxy for the db_manager singleton.
    This ensures the DatabaseManager is created only when first accessed,
    after environment variables are set (e.g., by pytest_configure or test setup).
    """
    _instance = None

    def _get_instance(self):
        if self._instance is None:
            self._instance = DatabaseManager()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get_instance(), name)

    def __setattr__(self, name, value):
        if name.startswith('_instance') or name == '_get_instance':
            super().__setattr__(name, value)
        else:
            setattr(self._get_instance(), name, value)


db_manager = _DatabaseManagerProxy()
