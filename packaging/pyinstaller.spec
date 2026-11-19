# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Build Specification for Anti-Matrix Billing V2 Desktop ERP.

Produces a standalone release bundle containing:
- PyQt5 + PyQtWebEngine desktop runtime
- Qt WebChannel communication bridge
- Frontend assets (index.html, styles.css, app.js, js/*, desktop/qwebchannel.js)
- Database migration engines (Alembic traditional & fast billing migrations)
- ReportLab PDF printing subsystem
- Strict data isolation ensuring runtime databases, logs, and backups are directed
  to the user's OS application data directory rather than the read-only bundle directory.
"""

import sys
import os
from pathlib import Path

block_cipher = None

# Root directory of the repository
PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), '..'))

# Collect static assets and migration directories
datas = [
    (os.path.join(PROJ_ROOT, 'index.html'), '.'),
    (os.path.join(PROJ_ROOT, 'styles.css'), '.'),
    (os.path.join(PROJ_ROOT, 'app.js'), '.'),
    (os.path.join(PROJ_ROOT, 'js'), 'js'),
    (os.path.join(PROJ_ROOT, 'desktop', 'qwebchannel.js'), 'desktop'),
    (os.path.join(PROJ_ROOT, 'traditional_alembic.ini'), '.'),
    (os.path.join(PROJ_ROOT, 'traditional_migrations'), 'traditional_migrations'),
    (os.path.join(PROJ_ROOT, 'alembic.ini'), '.'),
    (os.path.join(PROJ_ROOT, 'alembic'), 'alembic'),
    (os.path.join(PROJ_ROOT, 'assets'), 'assets'),
]

# Hidden imports required by dynamic loaders (Alembic, SQLAlchemy, PyQt, ReportLab)
hiddenimports = [
    # PyQt5 & WebEngine
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtNetwork',
    'PyQt5.QtWebChannel',
    'PyQt5.QtWebEngineWidgets',
    'PyQt5.QtPrintSupport',
    
    # Database and Migrations
    'sqlalchemy',
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.postgresql',
    'alembic',
    'alembic.config',
    'alembic.command',
    'alembic.script',
    'alembic.environment',
    
    # Internal Modules
    'core',
    'core.configuration',
    'core.logging_config',
    'db',
    'db.database',
    'db.models',
    'db.traditional_database',
    'db.traditional_models',
    'desktop',
    'desktop.main_window',
    'desktop.web_bridge',
    'services',
    'services.company_service',
    'services.traditional_auth_service',
    'services.traditional_payment_service',
    'services.traditional_financial_reconciliation_service',
    'services.traditional_accounting_service',
    'services.traditional_inventory_service',
    'services.billing_service',
    'services.catalogue_service',
    'services.voucher_print_service',
    
    # PDF & Imaging
    'reportlab',
    'reportlab.platypus',
    'reportlab.lib',
    'reportlab.pdfgen',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    
    # Utilities & Security
    'cryptography',
    'dotenv',
]

# Excluded packages to keep bundle clean and secure
excludes = [
    'pytest',
    'tests',
    'tests.traditional',
    'tests.fast_billing',
    'tests.staging',
    'tkinter',
    'matplotlib',
    'scipy',
    'numpy',
]

a = Analysis(
    [os.path.join(PROJ_ROOT, 'app.py')],
    pathex=[PROJ_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AntiMatrixBilling',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJ_ROOT, 'assets', 'app_icon.icns' if sys.platform == 'darwin' else 'app_icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AntiMatrixBilling',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='AntiMatrixBilling.app',
        icon=os.path.join(PROJ_ROOT, 'assets', 'app_icon.icns'),
        bundle_identifier='com.antimatrix.billing',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'NSRequiresAquaSystemAppearance': 'False',
            'CFBundleShortVersionString': '2.5.0',
            'CFBundleVersion': '2.5.0',
        },
    )
