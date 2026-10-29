# Desktop Packaging & Distribution Guide

## Anti Matrix Commercial Billing & POS System

This guide explains how to package the application into a standalone installer / executable for retail deployment on Windows and macOS.

---

### Prerequisites

* Python 3.11+
* PyInstaller 6.0+

Install packaging dependencies:
```bash
pip install pyinstaller
```

---

### 1. Building Standalone Executable on Windows

Run from the `Billing/` root directory on a Windows machine:

```powershell
pyinstaller --noconfirm --onedir --windowed `
  --name "AntiMatrixBilling" `
  --add-data "index.html;." `
  --add-data "styles.css;." `
  --add-data "app.js;." `
  --add-data "qwebchannel.js;." `
  --add-data "db/migrations;db/migrations" `
  app.py
```

The output will be created in `dist/AntiMatrixBilling/AntiMatrixBilling.exe`.

#### Creating Windows Inno Setup Installer
Wrap `dist/AntiMatrixBilling/` into an `.exe` setup installer using Inno Setup:
* Creates desktop shortcuts
* Installs USB barcode scanner & thermal printer drivers
* Configures permissions for `%APPDATA%\AntiMatrixBilling`

---

### 2. Building on macOS (Apple Silicon / Intel)

Run from the `Billing/` root directory on macOS:

```bash
pyinstaller --noconfirm --onedir --windowed \
  --name "AntiMatrixBilling" \
  --add-data "index.html:." \
  --add-data "styles.css:." \
  --add-data "app.js:." \
  --add-data "qwebchannel.js:." \
  --add-data "db/migrations:db/migrations" \
  app.py
```

The application bundle will be located at `dist/AntiMatrixBilling.app`.

---

### 3. File Assets Checklist

Ensure the following bundled assets are present alongside the executable:
* `index.html`
* `styles.css`
* `app.js`
* `qwebchannel.js`
* `db/migrations/001_initial_schema.sql`
