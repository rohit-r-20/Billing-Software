# Alpha Billing V2 — Application Database Connection Audit

## 1. Executive Summary

This document audits the complete runtime connection flow of the Alpha Billing desktop application, tracing database access from application entry point (`app.py`) through the PySide6/QtWebEngine shell, the `QWebChannel` JavaScript bridge (`desktop/web_bridge.py`), backend domain services (`services/`), and the centralized database management layer (`db/database.py`).

---

## 2. Desktop Application Connection Architecture & Flow Diagram

The application uses an isolated multi-layer architecture where the HTML/JS frontend has zero direct database drivers. All persistence actions travel through a Qt WebChannel bridge into Python domain services that execute through `DatabaseManager`.

```mermaid
flowchart TD
    subgraph UI_Layer["Frontend Layer (Chromium WebEngine)"]
        UI["HTML5 / JS Interface (index.html, app.js)"]
        BridgeClient["qwebchannel.js (window.backend)"]
        UI -->|QWebChannel JSON RPC| BridgeClient
    end

    subgraph Desktop_Shell["PySide6 Desktop Container"]
        App["app.py (QApplication Entrypoint)"]
        MainWindow["desktop/main_window.py (MainWindow)"]
        WebBridge["desktop/web_bridge.py (BackendBridge)"]
        
        App -->|1. check_health()| DBManager
        App -->|2. Instantiate| MainWindow
        MainWindow -->|Registers Object 'backend'| WebBridge
        BridgeClient <-->|IPC Qt Signal/Slot| WebBridge
    end

    subgraph Service_Layer["Backend Service Layer (Python)"]
        WebBridge --> AccountSvc["account_service.py"]
        WebBridge --> BillingSvc["billing_service.py"]
        WebBridge --> InventorySvc["inventory_service.py"]
        WebBridge --> SupplierSvc["supplier_service.py"]
        WebBridge --> CatalogueSvc["catalogue_service.py"]
        WebBridge --> ReportingSvc["reporting_service.py"]
    end

    subgraph Database_Layer["Database Abstraction Layer (db/database.py)"]
        AccountSvc -->|self.db.get_connection()| DBManager["DatabaseManager (db_manager)"]
        BillingSvc -->|self.db.get_connection()| DBManager
        InventorySvc -->|self.db.get_connection()| DBManager
        SupplierSvc -->|self.db.get_connection()| DBManager
        CatalogueSvc -->|self.db.get_connection()| DBManager
        ReportingSvc -->|self.db.get_connection()| DBManager
        
        DBManager -->|Config & Pool Settings| Config["core/configuration.py (AppConfig)"]
        DBManager -->|Engine Factory| Engine["SQLAlchemy 2.x Engine (QueuePool)"]
        DBManager -->|Session Factory| SessionFactory["sessionmaker / session_scope()"]
        DBManager -->|DBAPI Adapter| Adapter["PostgresConnectionAdapter (Psycopg 3)"]
    end

    subgraph PostgreSQL_Server["PostgreSQL Infrastructure"]
        Engine -->|SSL Encrypted Tunnel (port 5432)| PG[("Supabase / Self-Managed PostgreSQL 17.11")]
        Adapter -->|psycopg.connect(?sslmode=require)| PG
    end
```

---

## 3. Detailed Startup & Connection Flow Verification

### Step 1: Environment & Configuration Loading (`core/configuration.py`)
- When `app.py` or any module imports `core.configuration`, `load_dotenv(_BASE_DIR / ".env")` executes automatically.
- `AppConfig.get_database_url()` inspects `DATABASE_URL` (priority 1), `SUPABASE_DATABASE_URL` (priority 2), `ANTI_MATRIX_DATABASE_URL` (priority 3), and falls back to SQLite (`data/anti_matrix_billing.db`) only if no PostgreSQL configuration is present.
- `AppConfig.get_pool_config()` reads `DB_POOL_SIZE` (default 5), `DB_MAX_OVERFLOW` (default 10), `DB_POOL_TIMEOUT` (default 30s), and `DB_POOL_RECYCLE` (default 300s).

### Step 2: Database Manager Initialization (`db/database.py`)
- The singleton `db_manager = DatabaseManager()` is instantiated on first import.
- It determines the dialect: `self.is_postgres = True` if the URL starts with `postgresql` or `postgres`.
- It initializes the central SQLAlchemy 2.x engine:
  ```python
  self._engine = create_engine(
      norm_url,
      pool_pre_ping=True,
      pool_size=pool_opts["pool_size"],
      max_overflow=pool_opts["max_overflow"],
      pool_timeout=pool_opts["pool_timeout"],
      pool_recycle=pool_opts["pool_recycle"],
  )
  self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
  ```

### Step 3: Startup Health Check (`app.py`)
- `app.py` executes `health = db_manager.check_health()` before opening the desktop window.
- It tests round-trip execution of `SELECT 1 AS alive;`, measures latency, and retrieves server version and active schema.
- **Decoupled Startup**: Unlike previous versions which attempted automatic schema migration (`run_migrations()`) on startup, `app.py` now only performs non-destructive health diagnostics.

### Step 4: Window & Bridge Initialization (`desktop/main_window.py`)
- `MainWindow` creates `QWebEngineView`, hosts `index.html`, and initializes `QWebChannel`.
- It registers `self.bridge = BackendBridge(self)` under the identifier `"backend"`.
- The frontend JavaScript interacts with Python exclusively through `window.backend.<method>()`.
- **Frontend Isolation**: The frontend code has **no direct database credentials**, connection strings, or network sockets to PostgreSQL.

### Step 5: Backend Service Execution (`services/`)
- Domain services (`AccountService`, `BillingService`, `InventoryService`, `SupplierService`, `CatalogueService`) instantiate with `self.db = db or db_manager`.
- When handling operations, services call:
  ```python
  with self.db.get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute(sql, params)
  ```
- In PostgreSQL mode, `self.db.get_connection()` returns a `PostgresConnectionAdapter` wrapping a native **Psycopg 3** connection. Positional parameter placeholders `?` are automatically translated to `%s` via `translate_placeholders_to_percent_s()`.

---

## 4. Verification of Specific Safety & Operational Requirements

### 1. Does the desktop application initialize the PostgreSQL database manager?
**CONFIRMED**: Yes. When `DATABASE_URL` is set to PostgreSQL, `db_manager.is_postgres` evaluates to `True`, the SQLAlchemy engine connects using `postgresql+psycopg://`, and all service queries use Psycopg 3 connections.

### 2. Does the database manager create the correct SQLAlchemy engine?
**CONFIRMED**: Yes. A single `create_engine` factory is used with `QueuePool`, `pool_pre_ping=True`, and connection recycling. `db_manager.engine` returns the singleton engine instance.

### 3. Do backend services use the intended session factory?
**CONFIRMED**: Services currently use `self.db.get_connection()` which utilizes `PostgresConnectionAdapter` with contextual transactions (`__enter__` / `__exit__` with automatic rollback on error). For ORM models, `db_manager.session_scope()` provides transactional SQLAlchemy 2.x sessions.

### 4. Do UI components create their own database connections?
**CONFIRMED**: No. All UI components communicate via IPC calls across `QWebChannel` to `BackendBridge`. The frontend contains no database drivers, no credentials, and no network database sockets.

### 5. Is there a hidden SQLite fallback that silently handles business operations?
**CONFIRMED**: No. When `is_postgres` is True, `self.db.get_connection()` executes `psycopg.connect(...)`. If PostgreSQL is unreachable or fails, Psycopg raises an operational exception. **There is no silent catch-and-fallback to SQLite**.

### 6. Are database connection failures displayed clearly?
**PARTIAL (Requires Enhancement)**:
- At startup, `app.py` logs connection failures with `logger.error(f"Database connection error: {health.get('error')}")`.
- In `desktop/web_bridge.py`, all slot methods catch database exceptions and return `{"success": False, "error": str(e)}`.
- In the frontend, `app.js` displays a toast notification (`showToast(res.error, "error")`).
- **Gap Identified**: If the database is completely offline at application launch, `app.py` logs the error and proceeds to load the UI rather than presenting a modal native dialog (`QMessageBox.critical`) warning the user of the offline state before opening the POS screen.

### 7. Does application shutdown dispose the engine correctly?
**PARTIAL (Requires Enhancement)**:
- `db_manager.dispose()` is implemented and tested to drain the connection pool and dispose the SQLAlchemy engine.
- However, in `desktop/main_window.py`, `closeEvent()` stops the mobile scanner service but did not explicitly invoke `db_manager.dispose()`. Adding `db_manager.dispose()` to `closeEvent()` and registering an `atexit` hook ensures connection pool sockets are terminated cleanly upon OS-level application exit.
