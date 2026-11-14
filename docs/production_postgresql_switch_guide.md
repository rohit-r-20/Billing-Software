# Alpha Billing V2 — Production PostgreSQL Switch Guide

## 1. Overview

This guide outlines the exact, step-by-step procedure for transitioning Alpha Billing V2 from the Supabase development/testing database to a production PostgreSQL environment (e.g., self-hosted PostgreSQL, AWS RDS, GCP Cloud SQL, or on-premise dedicated server).

Because Alpha Billing V2 is engineered on a pure **portable PostgreSQL architecture** using **SQLAlchemy 2.x, Psycopg 3, and Alembic**, switching environments requires **zero code changes** in business logic, frontend code, or ORM models.

---

## 2. Production Switch Checklist

```mermaid
flowchart TD
    Step1["1. Provision Production PostgreSQL Server<br/>(v15, v16, or v17)"] --> Step2["2. Configure Network & SSL Certificates"]
    Step2 --> Step3["3. Update Production .env Configuration<br/>(DATABASE_ENV=production, DATABASE_URL)"]
    Step3 --> Step4["4. Apply Version-Controlled Alembic Migrations<br/>(alembic upgrade head)"]
    Step4 --> Step5["5. Perform Separately Approved Data Migration<br/>& Financial Reconciliation"]
    Step5 --> Step6["6. Execute Connection Health & Integrity Verification"]
    Step6 --> Step7["7. Launch Production Application"]
```

---

## 3. Step-by-Step Transition Procedure

### Step 1: Provision the Production Database
Ensure the production PostgreSQL instance meets the minimum requirements:
- **Version**: PostgreSQL 15, 16, or 17.
- **Extensions**: None required (standard ANSI PostgreSQL compliant).
- **Encoding**: UTF-8.
- **Collation**: `C` or standard system locale.

### Step 2: Configure Environment Variables (`.env`)
Update the `.env` file on the production deployment host:

```env
# ==============================================================================
# Alpha Billing - Production Environment Configuration
# ==============================================================================
DATABASE_ENV=production

# Production PostgreSQL Connection URI:
DATABASE_URL=postgresql+psycopg://alpha_admin:YOUR_SECURE_PASSWORD@db.alphabilling.internal:5432/alpha_billing_prod?sslmode=verify-full&sslrootcert=/path/to/server-ca.pem

# Production Connection Pool Parameters:
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=600

# Application Logging
APP_ENV=production
APP_LOG_LEVEL=WARNING
```

### Step 3: Run Alembic Schema Migrations
Initialize the complete database schema cleanly from version-controlled migrations:
```bash
# Verify target database URL resolution
.venv/bin/alembic current

# Apply migrations to head
.venv/bin/alembic upgrade head

# Verify head revision matches repository
.venv/bin/alembic heads
```

### Step 4: Verify Connection & Diagnostic Health
Execute the built-in diagnostic test to verify round-trip connectivity:
```bash
.venv/bin/python -c "
from db.database import db_manager
health = db_manager.check_health()
print('Health Status:', health)
assert health['healthy'] is True, 'Production database connection failed!'
"
```

### Step 5: Data Migration (When Authorized)
If historical business data is to be migrated from SQLite to the production database:
1. Create a protected, timestamped backup of the source SQLite database.
2. Execute the verified migration orchestrator:
   ```bash
   .venv/bin/python scripts/migrate_sqlite_to_supabase.py --sqlite data/anti_matrix_billing.db --target-url "$DATABASE_URL"
   ```
3. Verify reconciliation of invoice totals, tax registers, and stock balances.

---

## 4. What Remains 100% Unchanged

| Component | Status During Switch |
|---|---|
| **Python Backend (`app.py`, `core/*`)** | **Unchanged** |
| **Domain Services (`services/*`)** | **Unchanged** |
| **SQLAlchemy Models (`db/models.py`)** | **Unchanged** |
| **Desktop Bridge (`desktop/web_bridge.py`)** | **Unchanged** |
| **Frontend UI (`index.html`, `app.js`, `styles.css`)** | **Unchanged** |
| **Alembic Migration Scripts (`alembic/versions/*`)** | **Unchanged** |
