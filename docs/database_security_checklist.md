# Alpha Billing V2 — Database Security Checklist

## 1. Security Overview

Alpha Billing V2 enforces a strict security perimeter designed to protect business credentials, prevent data leaks, and secure both cloud-hosted (Supabase) and future on-premise PostgreSQL environments.

---

## 2. Security Audit Matrix

| # | Security Control Domain | Requirement / Standard | Implementation in Alpha Billing V2 | Verification Status |
|---|---|---|---|---|
| **1** | **Environment Credentials Isolation** | Database passwords and connection URIs must exist only in local `.env`. | Handled strictly in `core/configuration.py`. Loaded via `python-dotenv`. Never hardcoded in source. | **VERIFIED** |
| **2** | **Git Exclusion & Hygiene** | `.env` must never be committed or staged in Git. | `.env` is explicitly listed in `.gitignore`. Verified via `git status` that `.env` is untracked. | **VERIFIED** |
| **3** | **Template Sanitization** | Repository must maintain a clean `.env.example` with placeholders only. | `.env.example` contains clear placeholders (`[YOUR_PASSWORD]`, `[YOUR_PROJECT_REF]`) with zero secrets. | **VERIFIED** |
| **4** | **Frontend Boundary Protection** | JavaScript, HTML, and QWebChannel must not access database credentials. | `desktop/web_bridge.py` exposes strictly domain-level methods. Frontend never receives connection strings. | **VERIFIED** |
| **5** | **Privilege Minimization** | Never use Supabase `service_role` superuser key in client applications. | Desktop backend connects solely using standard PostgreSQL database credentials (`postgres` or custom app user). | **VERIFIED** |
| **6** | **Encrypted Transport (SSL/TLS)** | Remote cloud database traffic must be encrypted in transit. | All remote connection strings enforce `?sslmode=require` or `verify-full`. SSL handshake verified in connection tests. | **VERIFIED** |
| **7** | **Log Scrubbing & Credential Masking**| Passwords and connection secrets must never appear in log files or console. | `AppConfig.mask_database_url()` replaces URI passwords with `****` prior to logging or diagnostic reporting. | **VERIFIED** |
| **8** | **Transaction Atomicity & Rollback** | Incomplete, failed, or interrupted operations must not leave orphan records. | `session_scope()` and `PostgresConnectionAdapter` execute automatic `ROLLBACK` on unhandled exceptions. | **VERIFIED** |
| **9** | **Historical SQLite Protection** | The historical database must be protected from accidental modification or erasure. | SQLite database is opened with `mode=ro` (read-only) during inspections. Data migration is separate and non-destructive. | **VERIFIED** |
| **10**| **Decoupled Schema DDL** | Desktop startup must not automatically execute DDL or schema alterations. | `app.py` startup removes automatic `run_migrations()`, executing only non-destructive health checks. | **VERIFIED** |

---

## 3. Residual Security Recommendations for Production Deployment

1. **Dedicated Production User**:
   - For production self-hosted PostgreSQL, avoid using the `postgres` superuser.
   - Provision a dedicated application user (e.g. `alpha_billing_app`) with `GRANT SELECT, INSERT, UPDATE, DELETE` restricted to the application database tables only.
2. **SSL Certificate Pinning (`verify-full`)**:
   - In production, specify `sslmode=verify-full` and supply the root CA certificate (`sslrootcert=/etc/ssl/certs/db-ca.crt`) to prevent Man-in-the-Middle (MITM) attacks.
3. **Database Backup Encryption**:
   - Ensure automated physical and SQL backups (`backups/*.sql`, `backups/*.db`) are encrypted at rest with AES-256 before offsite replication.
