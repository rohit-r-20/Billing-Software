# Multi-Computer & Central Database Deployment Guide

## Anti Matrix Commercial Billing & POS System

This document outlines the deployment topology for retail stores requiring multiple cashier terminals operating simultaneously.

---

### Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │    Central Database / Server Host      │
                      │       PostgreSQL 15+ Server            │
                      │  (Transactions, Inventory, Ledgers)   │
                      └──────────────────┬─────────────────────┘
                                         │
             ┌───────────────────────────┼───────────────────────────┐
             │ LAN (Ethernet/Secure Wi-Fi)                           │
             ▼                                                       ▼
┌─────────────────────────┐                             ┌─────────────────────────┐
│     Cashier Terminal 1  │                             │     Cashier Terminal 2  │
│  - Anti Matrix Billing  │                             │  - Anti Matrix Billing  │
│  - Register: REG01      │                             │  - Register: REG02      │
│  - 80mm Thermal Printer │                             │  - 58mm Thermal Printer │
│  - USB HID Scanner      │                             │  - USB HID Scanner      │
└─────────────────────────┘                             └─────────────────────────┘
```

---

### 1. Single-Computer Mode (Default)
* **Database**: Local SQLite engine located at `data/anti_matrix_billing.db`.
* **Concurrency**: Optimized with SQLite Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and normal synchronous commits.
* **Use Case**: Small retail shops, vegetable stalls, single cashier counters.
* **Backups**: Automated daily snapshots to `backups/` and mirrored to external USB storage.

---

### 2. Multi-Cashier Network Mode (Supermarkets & Large Stores)

When multiple cashiers operate concurrently, a shared database server guarantees transactional consistency and prevents duplicate invoice numbers.

#### A. Database Server Setup (PostgreSQL)
1. Install PostgreSQL 15+ on the back-office or dedicated server:
   ```bash
   sudo apt update && sudo apt install postgresql postgresql-contrib
   ```
2. Create database and dedicated user:
   ```sql
   CREATE DATABASE anti_matrix_billing;
   CREATE USER antim_user WITH ENCRYPTED PASSWORD 'StrongSecretPasswordHere';
   GRANT ALL PRIVILEGES ON DATABASE anti_matrix_billing TO antim_user;
   ```
3. Enable remote connections in `postgresql.conf` and `pg_hba.conf`:
   ```conf
   # postgresql.conf
   listen_addresses = '*'

   # pg_hba.conf (allow LAN subnet)
   host    anti_matrix_billing    antim_user    192.168.1.0/24    scram-sha-256
   ```

#### B. Client Configuration
On each cashier terminal, configure the database URL via environment variable or in `config.json`:
```bash
export ANTI_MATRIX_DATABASE_URL="postgresql://antim_user:StrongSecretPasswordHere@192.168.1.50:5432/anti_matrix_billing"
```
Or set the parameter in `core/configuration.py`.

#### C. Concurrent Checkout Safety
* **Sequential Invoice Numbers**: Invoice numbers are scoped by `company_id`, `branch_id`, and `series`. In multi-cashier mode, terminal registers append their register code (e.g. `INV-REG01-001`, `INV-REG02-001`) or utilize an atomic PostgreSQL sequence:
  ```sql
  CREATE SEQUENCE pos_invoice_seq_comp0001 START 1;
  ```
* **Stock Concurrency**: Stock balance deductions use atomic updates:
  ```sql
  UPDATE stock_balances
  SET current_qty = current_qty - :sold_qty, last_updated = CURRENT_TIMESTAMP
  WHERE branch_id = :branch_id AND item_id = :item_id;
  ```
* **Network Interruption**: If the central database is unreachable, terminals display an alert preventing incomplete or ghost sales.

