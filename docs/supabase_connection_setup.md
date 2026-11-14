# Alpha Billing V2 — Supabase Connection Setup Guide

## 1. Overview

This document provides exact specifications and operational instructions for connecting Alpha Billing V2 to a **Supabase-hosted PostgreSQL** project for development and integration testing.

---

## 2. Supabase Connection Modes Explained

Supabase provides two distinct connection infrastructures. Understanding the distinction is vital to prevent application failure:

```mermaid
graph TD
    App["Alpha Billing Python Backend"]
    
    subgraph Direct ["1. Direct Connection (Port 5432)"]
        DirectHost["db.[project-ref].supabase.co:5432"]
        IPv6["Requires Native IPv6 Network Route<br/>Full PostgreSQL feature support"]
    end
    
    subgraph Pooler ["2. Supavisor Connection Pooler"]
        SessionPooler["Session Mode (Port 5432)<br/>aws-0-[region].pooler.supabase.com<br/>Persistent client sessions, prepared statements"]
        TxPooler["Transaction Mode (Port 6543)<br/>aws-0-[region].pooler.supabase.com<br/>Serverless only; NO prepared statements"]
    end
    
    App -->|Preferred for Desktop Billing| SessionPooler
    App -->|Direct IPv6 Route| DirectHost
    App -.->|NOT recommended for desktop clients| TxPooler
```

### Mode Comparison:

| Feature | Direct Connection | Supavisor Session Pooler | Supavisor Transaction Pooler |
|---|---|---|---|
| **Port** | `5432` | `5432` | `6543` |
| **Network Protocol** | **IPv6 Only** | **IPv4 & IPv6** | **IPv4 & IPv6** |
| **Host Format** | `db.[project-ref].supabase.co` | `aws-0-[region].pooler.supabase.com` | `aws-0-[region].pooler.supabase.com` |
| **User Format** | `postgres` | `postgres.[project-ref]` | `postgres.[project-ref]` |
| **Prepared Statements** | Supported | Supported | **NOT Supported** (Fails with Psycopg 3 prepared queries) |
| **Recommendation for Desktop ERP** | Suitable when IPv6 available | **Recommended for all networks** | For serverless web functions only |

---

## 3. Network & DNS Troubleshooting (The IPv6 Direct Route Issue)

During connection testing on macOS, the direct hostname `db.nxetowrecgjbpijdjpqd.supabase.co` exhibited intermittent DNS resolution errors:
```
[Errno 8] nodename nor servname provided, or not known
```

### Root Cause Analysis:
- Supabase direct database hostnames (`db.<project-ref>.supabase.co`) publish **AAAA records (IPv6) only**. They do not publish standard IPv4 A records.
- Local DHCP and Wi-Fi routers frequently use DNS forwarders (e.g., `10.196.9.72`) that do not query or forward AAAA records reliably.
- When tested with public DNS (`8.8.8.8` / `1.1.1.1`), the hostname resolved immediately to `2406:da14:18fe:3100::2c0c`.
- Direct connection to `[2406:da14:18fe:3100::2c0c]:5432` connected with **100% success** to PostgreSQL 17.11.

### Operational Resolution:
1. **Primary Recommendation**: Obtain the exact Supabase Session Pooler URL from the Supabase Dashboard:
   - Navigate to: **Project Settings -> Database -> Connection Pooling**.
   - Select **Mode: Session** (Port `5432`).
   - Copy the connection string.
2. **Alternative Direct IPv6 Resolution**:
   - If connecting directly, ensure your network adapter or system DNS includes `8.8.8.8` or `1.1.1.1` to enable AAAA record resolution, or specify the verified IPv6 address in development testing.

---

## 4. Configuration Instructions (`.env`)

Store credentials **exclusively** in the local `.env` file at the root of the project.

### Recommended Configuration Template:
```env
# ==============================================================================
# Alpha Billing - Development Environment Configuration
# ==============================================================================
DATABASE_ENV=development

# 1. Supabase Session Pooler (Port 5432 - Recommended):
DATABASE_URL=postgresql+psycopg://postgres.[YOUR_PROJECT_REF]:[YOUR_PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?sslmode=require

# 2. Supabase Direct Connection (Port 5432 - IPv6):
# DATABASE_URL=postgresql+psycopg://postgres:[YOUR_PASSWORD]@db.[YOUR_PROJECT_REF].supabase.co:5432/postgres?sslmode=require

# Application Settings
APP_ENV=development
APP_LOG_LEVEL=INFO
```

---

## 5. Security & Isolation Rules

- **Zero Git Leaks**: `.env` is listed in `.gitignore`. Never use `git add -f .env`.
- **Backend Isolation**: Credentials remain entirely within the Python process (`core/configuration.py`, `db/database.py`).
- **Frontend Protection**: The QWebChannel bridge (`desktop/web_bridge.py`) exposes domain methods (e.g. `save_invoice`, `search_items`) and never passes credentials, connection strings, or raw SQL capabilities to JavaScript.
- **Service-Role Key**: Never place the Supabase `service_role` secret in desktop configuration or frontend scripts.
