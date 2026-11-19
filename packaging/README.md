# Anti-Matrix Billing V2 — Release Packaging Guide

This guide details how to build and verify the release candidate standalone package for staging and production testing.

## Overview

Anti-Matrix Billing V2 is a hybrid desktop application combining:
- **PyQt5 & QtWebEngine**: Native cross-platform desktop wrapper with hardware-accelerated Chromium rendering.
- **HTML5/ES6 Frontend**: Single Page Application communicating through Qt WebChannel.
- **SQLAlchemy & SQLite/PostgreSQL Engine**: High-performance multi-modal persistence (Fast Billing POS and Traditional ERP Accounting).
- **Alembic Database Migrations**: Automated zero-downtime database schema provisioning.

## Packaging Requirements

1. **Python Environment**: Python 3.10–3.12 (Recommended: Python 3.11).
2. **PyInstaller**: `pip install pyinstaller`.
3. **Platform Libraries**:
   - macOS: Command Line Tools (`xcode-select --install`).
   - Windows: Visual C++ Redistributable 2015–2022.
   - Linux: `libgl1-mesa-dev`, `libxcb-*`, `libnss3`.

## Packaging Steps

From the repository root:

```bash
# 1. Activate Virtual Environment
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows

# 2. Verify all tests pass
pytest tests/staging/ tests/traditional/ tests/fast_billing/ -q

# 3. Build Desktop Application Bundle
pyinstaller packaging/pyinstaller.spec --distpath dist --workpath build

# 4. Verify Built Artifact
# On macOS: dist/AntiMatrixBilling.app
# On Linux/Windows: dist/AntiMatrixBilling/
```

## Runtime Data Directory Isolation

When running in frozen bundle mode:
- The installation/bundle directory is **strictly read-only**.
- All operational data (SQLite databases, logs, recovery tokens, backups) are automatically directed to the platform-standard application data location:
  - **macOS**: `~/Library/Application Support/AntiMatrixBilling/data`
  - **Windows**: `%APPDATA%\AntiMatrixBilling\data`
  - **Linux**: `~/.local/share/anti-matrix-billing/data`
- Can be overridden using environment variable `APP_DATA_DIR` or `ANTI_MATRIX_DATA_DIR`.

## Staging Mode Execution

To launch the packaged binary in Staging profile:

```bash
# macOS
APP_ENV=staging open dist/AntiMatrixBilling.app

# Linux
APP_ENV=staging ./dist/AntiMatrixBilling/AntiMatrixBilling

# Windows (PowerShell)
$env:APP_ENV="staging"; .\dist\AntiMatrixBilling\AntiMatrixBilling.exe
```

When `APP_ENV=staging` is set, the application will:
1. Initialize `staging_anti_matrix_billing.db` and `staging_traditional_billing.db`.
2. Strictly reject any configuration attempting to access `anti_matrix_billing.db` or `traditional_billing.db`.
3. Display `[STAGING]` badge in application title and audit logs.
