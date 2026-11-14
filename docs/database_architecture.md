# Alpha Billing V2 — Database Abstraction Architecture

## 1. Architectural Blueprint & Core Philosophy

Alpha Billing V2 employs a **strictly decoupled, portable database abstraction architecture** designed for enterprise desktop billing. The architecture ensures that switching between **Supabase PostgreSQL** (for development and cloud testing) and a **self-managed or on-premise PostgreSQL server** (for production deployment) requires zero modifications to business logic, UI components, transaction services, or database models.

```mermaid
graph TD
    UI["PyQt5 / QWebEngine Frontend<br/>(HTML5 / CSS / JS / QWebChannel)"]
    Bridge["Desktop Web Bridge<br/>(desktop/web_bridge.py)"]
    Services["Domain Service Layer<br/>(Billing, Purchase, Inventory, Accounts)"]
    DBMgr["Central Database Manager<br/>(db/database.py)"]
    Config["Environment Configuration<br/>(core/configuration.py)"]
    Engine["SQLAlchemy 2.x Engine Factory<br/>& Connection Pool"]
    Session["Sessionmaker Factory<br/>& session_scope() Context Manager"]
    DBAPI["Psycopg 3 Adapter Layer<br/>(PostgresConnectionAdapter)"]
    Supabase[("Supabase PostgreSQL<br/>(Dev & Cloud Testing)")]
    SelfHosted[("Self-Managed PostgreSQL<br/>(Production Deployment)")]
    SQLite[("Historical SQLite Archive<br/>(Read-Only / Unchanged)")]

    UI -->|Async JSON-RPC| Bridge
    Bridge --> Services
    Services --> DBMgr
    Config -.->|DATABASE_ENV / DATABASE_URL| DBMgr
    DBMgr --> Engine
    DBMgr --> Session
    DBMgr --> DBAPI
    Engine -->|Driver: postgresql+psycopg| Supabase
    Engine -.->|Driver: postgresql+psycopg| SelfHosted
    DBMgr -.->|Historical Fallback| SQLite
```

---

## 2. Abstraction Layer Components

### 2.1 Central Configuration (`core/configuration.py`)
All database settings are driven strictly by environment variables parsed via `python-dotenv`:
- **`DATABASE_ENV`**: Defines the active tier (`development`, `testing`, `production`).
- **`DATABASE_URL`**: Canonical 12-factor connection URI (`postgresql+psycopg://user:password@host:port/dbname?sslmode=...`).
- **Connection Pool Parameters**: Configurable via environment variables without hardcoded constants:
  - `DB_POOL_SIZE`: Default `5` (conservative for desktop billing nodes).
  - `DB_MAX_OVERFLOW`: Default `10`.
  - `DB_POOL_TIMEOUT`: Default `30` seconds.
  - `DB_POOL_RECYCLE`: Default `300` seconds (recycles connections every 5 minutes to prevent stale sockets across NAT/firewalls).
  - `pool_pre_ping=True`: Probes connections with `SELECT 1` before checkout, preventing stale socket errors.
- **Credential Masking**: `AppConfig.mask_database_url()` intercepts connection strings and scrubs passwords and tokens before emitting to logs, UI bridge, or diagnostics.

### 2.2 Central Database Manager (`db/database.py`)
Provides single points of entry for both ORM and direct DBAPI access:
1. **Single Engine Factory**: Lazily instantiates and caches a single `sqlalchemy.Engine` with the normalized `postgresql+psycopg` driver.
2. **Single Sessionmaker Factory**: Produces SQLAlchemy 2.x `Session` instances with `expire_on_commit=False`.
3. **Transactional Scope Manager (`session_scope()`)**:
   ```python
   @contextmanager
   def session_scope(self):
       session = self.get_session()
       try:
           yield session
           session.commit()
       except Exception as err:
           session.rollback()
           logger.error(f"Transaction rolled back: {err}")
           raise
       finally:
           session.close()
   ```
4. **Safe Connection Disposal (`dispose()`)**: Disposes connection pool resources cleanly during application teardown.
5. **Connection Diagnostics & Health Checks (`check_health()`)**: Measures live latency in milliseconds, checks schema readiness, and returns health metadata without exposing credentials.
6. **DBAPI Compatibility Adapter (`PostgresConnectionAdapter`, `PostgresRow`)**: Provides standard Python DBAPI cursor semantics for existing services with automatic positional parameter translation (`?` -> `%s`) and row dictionary access.

---

## 3. Decoupling Migrations from Application Startup

In legacy prototypes, schema migrations were invoked automatically every time the desktop application was launched. In Alpha Billing V2, this is strictly decoupled:
- **Application Startup (`app.py`)**: Executes only a fast, non-destructive connection health check (`db_manager.check_health()`). It verifies network readiness and reports latency. **No DDL statements or schema alterations are executed on startup.**
- **Schema Lifecycle**: Handled exclusively through version-controlled **Alembic migrations** executed via CLI or administrative scripts (`alembic upgrade head`).

---

## 4. Portability Guarantee

| Requirement | Supabase Dev / Test | Future Self-Managed Production |
|---|---|---|
| **Dialect & Driver** | PostgreSQL 17 / Psycopg 3 | PostgreSQL 15+ / Psycopg 3 |
| **SQLAlchemy Engine** | Same (`postgresql+psycopg`) | Same (`postgresql+psycopg`) |
| **ORM Models** | Same (`db/models.py`) | Same (`db/models.py`) |
| **Service Layer** | Same (`services/*`) | Same (`services/*`) |
| **Alembic Migrations** | Same (`alembic/versions/*`) | Same (`alembic/versions/*`) |
| **Configuration Switch** | `DATABASE_URL` pointing to Supabase | `DATABASE_URL` pointing to production host |
